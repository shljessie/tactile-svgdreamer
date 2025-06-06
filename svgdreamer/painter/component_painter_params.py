# -*- coding: utf-8 -*-
# Author: ximing
# Description: content painter and optimizer
# Copyright (c) 2023, XiMing Xing.
# License: MIT License

import copy
import math
import random
import pathlib
from typing import Dict, Tuple

from shapely.geometry.polygon import Polygon
from omegaconf import DictConfig
import numpy as np
import pydiffvg
import torch
from torch.optim.lr_scheduler import LambdaLR

from svgdreamer.painter import (SparseCoordInit, RandomCoordInit, NaiveCoordInit, get_sdf)
from svgdreamer.libs import get_optimizer


class CompPainter:

    def __init__(
            self,
            style: str,
            target_img: torch.Tensor,
            canvas_size: Tuple[int, int] = (600, 600),
            num_segments: int = 4,
            segment_init: str = 'circle',
            radius: int = 20,
            n_grid: int = 32,
            stroke_width: int = 3,
            path_svg=None,
            device=None,
            attn_init: bool = False,
            attention_map: torch.Tensor = None,
            attn_prob_tau: float = None,
    ):
        self.style = style
        self.device = device
        self.target_img = target_img
        self.path_svg = path_svg

        # curve params
        self.num_segments = num_segments
        self.segment_init = segment_init
        self.radius = radius

        self.canvas_width, self.canvas_height = canvas_size
        """pixelart params"""
        self.n_grid = n_grid  # divide the canvas into n grids
        self.pixel_per_grid = self.canvas_width // self.n_grid
        """sketch params"""
        self.stroke_width = stroke_width
        """iconography params"""
        self.color_ref = None

        self.shapes = []  # record all paths
        self.shape_groups = []
        self.cur_shapes, self.cur_shape_groups = [], []  # record the current optimized path
        self.point_vars = []
        self.color_vars = []
        self.width_vars = []

        # init
        self.attention_map = attention_map
        self.attn_init = attn_init
        self.attn_prob_tau = attn_prob_tau
        self.select_inds = None
        self.pos_init_method = None

        # background
        self.para_bg = torch.tensor([1., 1., 1.], requires_grad=False, device=self.device)
        # count the number of strokes
        self.strokes_counter = 0  # counts the number of calls to "get_path"

    def attn_init_points(self, num_paths, mask=None):
        attn_map = (self.attention_map - self.attention_map.min()) / \
                   (self.attention_map.max() - self.attention_map.min())

        attn_map_soft = np.copy(attn_map)
        attn_map_soft[attn_map > 0] = softmax_t(attn_map[attn_map > 0], tau=self.attn_prob_tau)
        # for visualizing
        attn_thresh = np.copy(attn_map_soft)
        # the probabilities associated with each entry in attn_map
        attn_map_soft /= np.sum(attn_map_soft)
        # select points
        k = num_paths

        # select k points randomly
        positions = np.where(mask == 1)
        positions = np.stack(positions, axis=1)
        np.random.shuffle(positions)
        positions = positions[:k]

        # note: only use to visual
        visual_coords = np.copy(positions)

        canvas_coords = np.copy(positions)
        canvas_coords[:, [0, 1]] = canvas_coords[:, [1, 0]]
        self.select_inds = canvas_coords

        # for visualizing
        return attn_thresh, visual_coords

    def component_wise_path_init(self, pred, init_type: str = 'sparse'):
        if init_type == 'random':
            self.pos_init_method = RandomCoordInit(self.canvas_height, self.canvas_width)

        elif init_type == 'sparse':
            assert self.target_img is not None  # target_img as GT
            # when initialized for the first time, the render result is None
            if pred is None:
                pred = self.para_bg.view(1, -1, 1, 1).repeat(1, 1, self.canvas_height, self.canvas_width)
            # then pred is the render result
            self.pos_init_method = SparseCoordInit(pred, self.target_img)

        elif init_type == 'naive':
            assert self.target_img is not None  # target_img as GT
            if pred is None:
                pred = self.para_bg.view(1, -1, 1, 1).repeat(1, 1, self.canvas_height, self.canvas_width)
            self.pos_init_method = NaiveCoordInit(pred, self.target_img)

        else:
            raise NotImplementedError(f"'{init_type}' is not support.")

    def init_image(self, num_paths=0):
        self.cur_shapes, self.cur_shape_groups = [], []

        if self.style in ['pixelart', 'low-poly']:  # update path definition
            num_paths = self.n_grid

        num_paths_exists = 0
        if self.path_svg is not None and pathlib.Path(self.path_svg).exists():
            print(f"-> init svg from `{self.path_svg}` ...")

            self.canvas_width, self.canvas_height, self.shapes, self.shape_groups = self.load_svg(self.path_svg)
            self.cur_shapes, self.cur_shape_groups = self.shapes, self.shape_groups
            # if you want to add more strokes to existing ones and optimize on all of them
            num_paths_exists = len(self.shapes)

        for i in range(num_paths_exists, num_paths):
            if self.style == 'iconography':
                path = self.get_path()
                self.shapes.append(path)
                self.cur_shapes.append(path)

                wref, href = self.color_ref
                wref = max(0, min(int(wref), self.canvas_width - 1))
                href = max(0, min(int(href), self.canvas_height - 1))
                fill_color_init = list(self.target_img[0, :, href, wref]) + [1.]
                fill_color_init = torch.FloatTensor(fill_color_init)
                path_group = pydiffvg.ShapeGroup(
                    shape_ids=torch.tensor([len(self.shapes) - 1]),
                    fill_color=fill_color_init,
                    stroke_color=None
                )
                self.shape_groups.append(path_group)
                self.cur_shape_groups.append(path_group)

            elif self.style in ['pixelart', 'low-poly']:
                fill_color_init = torch.FloatTensor(np.random.uniform(size=[4]))
                fill_color_init[-1] = 1.0

                for j in range(num_paths):
                    path = self.get_path(coord=[i, j])
                    self.shapes.append(path)
                    self.cur_shapes.append(path)

                    path_group = pydiffvg.ShapeGroup(
                        shape_ids=torch.LongTensor([i * num_paths + j]),
                        fill_color=fill_color_init,
                        stroke_color=None,
                    )
                    self.shape_groups.append(path_group)
                    self.cur_shape_groups.append(path_group)

            elif self.style in ['sketch', 'ink', 'tactile']:
                path = self.get_path()
                self.shapes.append(path)
                self.cur_shapes.append(path)

                stroke_color_init = torch.tensor([0.0, 0.0, 0.0, 1.0])
                path_group = pydiffvg.ShapeGroup(
                    shape_ids=torch.tensor([len(self.shapes) - 1]),
                    fill_color=None,
                    stroke_color=stroke_color_init
                )
                self.shape_groups.append(path_group)
                self.cur_shape_groups.append(path_group)

            elif self.style == 'painting':
                path = self.get_path()
                self.shapes.append(path)
                self.cur_shapes.append(path)

                wref, href = self.color_ref
                wref = max(0, min(int(wref), self.canvas_width - 1))
                href = max(0, min(int(href), self.canvas_height - 1))
                stroke_color_init = list(self.target_img[0, :, href, wref]) + [1.]
                path_group = pydiffvg.ShapeGroup(
                    shape_ids=torch.tensor([len(self.shapes) - 1]),
                    fill_color=None,
                    stroke_color=stroke_color_init
                )
                self.shape_groups.append(path_group)
                self.cur_shape_groups.append(path_group)

        img = self.render_warp()
        img = img[:, :, 3:4] * img[:, :, :3] + self.para_bg * (1 - img[:, :, 3:4])
        img = img.unsqueeze(0)  # convert img from HWC to NCHW
        img = img.permute(0, 3, 1, 2).to(self.device)  # NHWC -> NCHW
        return img

    def get_image(self, step: int = 0):
        img = self.render_warp(step)
        img = img[:, :, 3:4] * img[:, :, :3] + self.para_bg * (1 - img[:, :, 3:4])
        img = img.unsqueeze(0)  # convert img from HWC to NCHW
        img = img.permute(0, 3, 1, 2).to(self.device)  # NHWC -> NCHW
        return img

    def get_path(self, coord=None):
        num_segments = self.num_segments

        points = []
        if self.style == 'iconography':
            num_control_points = [2] * num_segments
            # init segment
            if self.segment_init == 'circle':
                radius = self.radius if self.radius is not None else np.random.uniform(0.5, 1)

                if self.attn_init:
                    center = self.select_inds[self.strokes_counter]  # shape: (2,)
                else:
                    center = (random.random(), random.random()) \
                        if self.pos_init_method is None else self.pos_init_method()

                bias = center
                self.color_ref = copy.deepcopy(bias)

                points = get_circle_coordinates(center, radius, k=num_segments * 3)
                points = torch.FloatTensor(points)
            else:
                if self.attn_init:
                    p0 = self.select_inds[self.strokes_counter]
                else:
                    p0 = self.pos_init_method()

                self.color_ref = copy.deepcopy(p0)
                points.append(p0)
                for j in range(num_segments):
                    radius = self.radius
                    p1 = (p0[0] + radius * np.random.uniform(-0.5, 0.5),
                          p0[1] + radius * np.random.uniform(-0.5, 0.5))
                    p2 = (p1[0] + radius * np.random.uniform(-0.5, 0.5),
                          p1[1] + radius * np.random.uniform(-0.5, 0.5))
                    p3 = (p2[0] + radius * np.random.uniform(-0.5, 0.5),
                          p2[1] + radius * np.random.uniform(-0.5, 0.5))
                    points.append(p1)
                    points.append(p2)
                    if j < num_segments - 1:
                        points.append(p3)
                        p0 = p3
                points = torch.FloatTensor(points)

            path = pydiffvg.Path(num_control_points=torch.LongTensor(num_control_points),
                                 points=points,
                                 stroke_width=torch.tensor(0.0),
                                 is_closed=True)
        elif self.style in ['sketch', 'painting', 'ink', 'tactile']:
            num_control_points = torch.zeros(num_segments, dtype=torch.long) + 2
            points = []

            if self.attn_init:
                p0 = self.select_inds[self.strokes_counter]
            else:
                p0 = (random.random(), random.random()) \
                    if self.pos_init_method is None else self.pos_init_method()

            self.color_ref = copy.deepcopy(p0)

            points.append(p0)
            for j in range(num_segments):
                radius = 0.1
                p1 = (p0[0] + radius * (random.random() - 0.5), p0[1] + radius * (random.random() - 0.5))
                p2 = (p1[0] + radius * (random.random() - 0.5), p1[1] + radius * (random.random() - 0.5))
                p3 = (p2[0] + radius * (random.random() - 0.5), p2[1] + radius * (random.random() - 0.5))
                points.append(p1)
                points.append(p2)
                points.append(p3)
                p0 = p3
            points = torch.tensor(points).to(self.device)

            if not self.attn_init:
                points[:, 0] *= self.canvas_width
                points[:, 1] *= self.canvas_height

            path = pydiffvg.Path(num_control_points=torch.LongTensor(num_control_points),
                                 points=points,
                                 stroke_width=torch.tensor(self.stroke_width),
                                 is_closed=False)
        elif self.style == 'pixelart':
            x = coord[0] * self.pixel_per_grid
            y = coord[1] * self.pixel_per_grid
            points = torch.FloatTensor([
                [x, y],
                [x + self.pixel_per_grid, y],
                [x + self.pixel_per_grid, y + self.pixel_per_grid],
                [x, y + self.pixel_per_grid]
            ]).to(self.device)
            path = pydiffvg.Polygon(points=points,
                                    stroke_width=torch.tensor(0.0),
                                    is_closed=True)

        self.strokes_counter += 1
        return path

    def clip_curve_shape(self):
        for group in self.shape_groups:
            group.fill_color.data.clamp_(0.0, 1.0)

    def reinitialize_paths(self,
                           reinit_path: bool = False,
                           opacity_threshold: float = None,
                           area_threshold: float = None,
                           fpath: pathlib.Path = None):
        """
        reinitialize paths, also known as 'Reinitializing paths' in VectorFusion paper.

        Args:
            reinit_path: whether to reinitialize paths or not.
            opacity_threshold: Threshold of opacity.
            area_threshold: Threshold of the closed polygon area.
            fpath: The path to save the reinitialized SVG.
        """
        if self.style == 'iconography' and reinit_path:
            # re-init by opacity_threshold
            select_path_ids_by_opc = []
            if opacity_threshold != 0 and opacity_threshold is not None:
                def get_keys_below_threshold(my_dict, threshold):
                    keys_below_threshold = [key for key, value in my_dict.items() if value < threshold]
                    return keys_below_threshold

                opacity_record_ = {group.shape_ids.item(): group.fill_color.data[-1].item()
                                   for group in self.cur_shape_groups}
                # print("-> opacity_record: ", opacity_record_)
                print("-> opacity_record: ", [f"{k}: {v:.3f}" for k, v in opacity_record_.items()])
                select_path_ids_by_opc = get_keys_below_threshold(opacity_record_, opacity_threshold)
                print("select_path_ids_by_opc: ", select_path_ids_by_opc)

            # remove path by area_threshold
            select_path_ids_by_area = []
            if area_threshold != 0 and area_threshold is not None:
                area_records = [Polygon(shape.points.detach().numpy()).area for shape in self.cur_shapes]
                # print("-> area_records: ", area_records)
                print("-> area_records: ", ['%.2f' % i for i in area_records])
                for i, shape in enumerate(self.cur_shapes):
                    if Polygon(shape.points.detach().numpy()).area < area_threshold:
                        select_path_ids_by_area.append(shape.id)
                print("select_path_ids_by_area: ", select_path_ids_by_area)

            # re-init paths
            reinit_union = list(set(select_path_ids_by_opc + select_path_ids_by_area))
            if len(reinit_union) > 0:
                for i, path in enumerate(self.cur_shapes):
                    if path.id in reinit_union:
                        self.cur_shapes[i] = self.get_path()
                for i, group in enumerate(self.cur_shape_groups):
                    shp_ids = group.shape_ids.cpu().numpy().tolist()
                    if set(shp_ids).issubset(reinit_union):
                        fill_color_init = torch.FloatTensor(np.random.uniform(size=[4]))
                        fill_color_init[-1] = np.random.uniform(0.7, 1)
                        stroke_color_init = torch.FloatTensor(np.random.uniform(size=[4]))
                        self.cur_shape_groups[i] = pydiffvg.ShapeGroup(
                            shape_ids=torch.tensor(list(shp_ids)),
                            fill_color=fill_color_init,
                            stroke_color=stroke_color_init)
                # save reinit svg
                self.save_svg(fpath)

            print("-" * 40)

    def render_warp(self, seed=0):
        scene_args = pydiffvg.RenderFunction.serialize_scene(
            self.canvas_width, self.canvas_height, self.shapes, self.shape_groups
        )
        _render = pydiffvg.RenderFunction.apply
        img = _render(self.canvas_width,  # width
                      self.canvas_height,  # height
                      2,  # num_samples_x
                      2,  # num_samples_y
                      seed,  # seed
                      None,
                      *scene_args)
        return img

    def calc_distance_weight(self, loss_weight_keep):
        shapes_forsdf = copy.deepcopy(self.cur_shapes)
        shape_groups_forsdf = copy.deepcopy(self.cur_shape_groups)
        for si in shapes_forsdf:
            si.stroke_width = torch.FloatTensor([0]).to(self.device)
        for sg_idx, sgi in enumerate(shape_groups_forsdf):
            sgi.fill_color = torch.FloatTensor([1, 1, 1, 1]).to(self.device)
            sgi.shape_ids = torch.LongTensor([sg_idx]).to(self.device)

        sargs_forsdf = pydiffvg.RenderFunction.serialize_scene(
            self.canvas_width, self.canvas_height, shapes_forsdf, shape_groups_forsdf
        )
        _render = pydiffvg.RenderFunction.apply
        with torch.no_grad():
            im_forsdf = _render(self.canvas_width,  # width
                                self.canvas_height,  # height
                                2,  # num_samples_x
                                2,  # num_samples_y
                                0,  # seed
                                None,
                                *sargs_forsdf)

        # use alpha channel is a trick to get 0-1 image
        im_forsdf = (im_forsdf[:, :, 3]).detach().cpu().numpy()
        loss_weight = get_sdf(im_forsdf, normalize='to1')
        loss_weight += loss_weight_keep
        loss_weight = np.clip(loss_weight, 0, 1)
        loss_weight = torch.FloatTensor(loss_weight).to(self.device)
        return loss_weight

    def set_points_parameters(self, id_delta=0):
        self.point_vars = []
        for i, path in enumerate(self.cur_shapes):
            path.id = i + id_delta  # set point id
            path.points.requires_grad = True
            self.point_vars.append(path.points)

    def get_point_params(self):
        return self.point_vars

    def set_color_parameters(self):
        self.color_vars = []
        for i, group in enumerate(self.cur_shape_groups):
            if group.fill_color is not None:
                group.fill_color.requires_grad = True
                self.color_vars.append(group.fill_color)
            if group.stroke_color is not None:
                group.stroke_color.requires_grad = True
                self.color_vars.append(group.stroke_color)

    def get_color_params(self):
        return self.color_vars

    def set_width_parameters(self):
        # stroke`s width optimization
        self.width_vars = []
        for i, path in enumerate(self.shapes):
            path.stroke_width.requires_grad = True
            self.width_vars.append(path.stroke_width)

    def get_width_params(self):
        return self.width_vars

    def save_svg(self, fpath):
        pydiffvg.save_svg(f'{fpath}',
                          self.canvas_width,
                          self.canvas_height,
                          self.shapes,
                          self.shape_groups)

    def load_svg(self, path_svg):
        canvas_width, canvas_height, shapes, shape_groups = pydiffvg.svg_to_scene(path_svg)
        return canvas_width, canvas_height, shapes, shape_groups


def softmax_t(x, tau=0.2):
    e_x = np.exp(x / tau)
    return e_x / e_x.sum()


def get_circle_coordinates(center, radius, k):
    coordinates = []
    cx, cy = center
    angle = 2 * math.pi / k

    for i in range(k):
        theta = i * angle  # cur angle
        x = cx + radius * math.cos(theta)  # x
        y = cy + radius * math.sin(theta)  # y
        coordinates.append((x, y))

    return coordinates


class LinearDecayLRLambda:

    def __init__(self, init_lr, keep_ratio, decay_every, decay_ratio):
        self.init_lr = init_lr
        self.keep_ratio = keep_ratio
        self.decay_every = decay_every
        self.decay_ratio = decay_ratio

    def __call__(self, n):
        if n < self.keep_ratio * self.decay_every:
            return self.init_lr

        decay_time = n // self.decay_every
        decay_step = n % self.decay_every
        lr_s = self.decay_ratio ** decay_time
        lr_e = self.decay_ratio ** (decay_time + 1)
        r = decay_step / self.decay_every
        lr = lr_s * (1 - r) + lr_e * r
        return lr


class CompPainterOptimizer:

    def __init__(self,
                 renderer: CompPainter,
                 style: str,
                 num_iter: int,
                 lr_config: DictConfig,
                 optim_bg: bool = False):
        self.renderer = renderer
        self.style = style
        self.num_iter = num_iter
        self.lr_config = lr_config
        schedule_cfg = self.lr_config.schedule
        self.optim_bg = optim_bg

        if style == 'iconography':
            self.optim_point, self.optim_color, self.optim_width = True, True, False
            self.point_lr_lambda = LinearDecayLRLambda(self.lr_config.point, schedule_cfg.keep_ratio,
                                                       self.num_iter, schedule_cfg.decay_ratio)
        if style == 'pixelart':
            self.optim_point, self.optim_color, self.optim_width = False, True, False
            self.point_lr_lambda = None
        if style == 'sketch':
            self.optim_point, self.optim_color, self.optim_width = True, False, False
            self.point_lr_lambda = LinearDecayLRLambda(self.lr_config.point, schedule_cfg.keep_ratio,
                                                       self.num_iter, schedule_cfg.decay_ratio)
        if style == 'ink':
            self.optim_point, self.optim_color, self.optim_width = True, False, True
            self.point_lr_lambda = LinearDecayLRLambda(self.lr_config.point, schedule_cfg.keep_ratio,
                                                       self.num_iter, schedule_cfg.decay_ratio)
        if style == 'painting':
            self.optim_point, self.optim_color, self.optim_width = True, True, True
            self.point_lr_lambda = LinearDecayLRLambda(self.lr_config.point, schedule_cfg.keep_ratio,
                                                       self.num_iter, schedule_cfg.decay_ratio)
        if style == 'tactile':
            self.optim_point, self.optim_color, self.optim_width = True, False, True
            self.point_lr_lambda = LinearDecayLRLambda(self.lr_config.point, schedule_cfg.keep_ratio,
                                                       self.num_iter, schedule_cfg.decay_ratio)

        self.point_optimizer = None
        self.color_optimizer = None
        self.width_optimizer = None
        self.bg_optimizer = None

        self.point_scheduler = None

    def init_optimizers(self, pid_delta=0):
        optim_cfg = self.lr_config.optim
        optim_name = optim_cfg.name

        params = {}
        if self.optim_point:
            self.renderer.set_points_parameters(pid_delta)
            params['point'] = self.renderer.get_point_params()

            if len(params['point']) > 0:
                self.point_optimizer = get_optimizer(optim_name, params['point'], self.lr_config.point, optim_cfg)
            if self.point_lr_lambda is not None:
                self.point_scheduler = LambdaLR(self.point_optimizer, lr_lambda=self.point_lr_lambda, last_epoch=-1)

        if self.optim_color:
            self.renderer.set_color_parameters()
            params['color'] = self.renderer.get_color_params()
            if len(params['color']) > 0:
                self.color_optimizer = get_optimizer(optim_name, params['color'], self.lr_config.color, optim_cfg)

        if self.optim_width:
            self.renderer.set_width_parameters()
            params['width'] = self.renderer.get_width_params()
            if len(params['width']) > 0:
                self.width_optimizer = get_optimizer(optim_name, params['width'], self.lr_config.width, optim_cfg)

        if self.optim_bg:
            self.renderer.para_bg.requires_grad = True
            self.bg_optimizer = get_optimizer(optim_name, self.renderer.para_bg, self.lr_config.bg, optim_cfg)

    def update_lr(self):
        if self.point_scheduler is not None:
            self.point_scheduler.step()

    def zero_grad_(self):
        if self.point_optimizer is not None:
            self.point_optimizer.zero_grad()
        if self.color_optimizer is not None:
            self.color_optimizer.zero_grad()
        if self.width_optimizer is not None:
            self.width_optimizer.zero_grad()
        if self.bg_optimizer is not None:
            self.bg_optimizer.zero_grad()

    def step_(self):
        if self.point_optimizer is not None:
            self.point_optimizer.step()
        if self.color_optimizer is not None:
            self.color_optimizer.step()
        if self.width_optimizer is not None:
            self.width_optimizer.step()
        if self.bg_optimizer is not None:
            self.bg_optimizer.step()

    def get_lr(self) -> Dict:
        lr = {}
        if self.point_optimizer is not None:
            lr['pnt'] = self.point_optimizer.param_groups[0]['lr']
        if self.color_optimizer is not None:
            lr['clr'] = self.color_optimizer.param_groups[0]['lr']
        if self.width_optimizer is not None:
            lr['wd'] = self.width_optimizer.param_groups[0]['lr']
        if self.bg_optimizer is not None:
            lr['bg'] = self.bg_optimizer.param_groups[0]['lr']
        return lr
