import torch
from PIL import Image
import numpy as np
import pydiffvg
import os
import pathlib

import ImageReward as RM
from ImageReward.ImageReward import ImageReward

class TactileReward:
    def __init__(self, reward_path='./checkpoint/ImageReward'):
        # Initialize the base ImageReward model using the load function
        # This handles downloading models if they don't exist
        try:
            self.base_reward = RM.load("ImageReward-v1.0", 
                                      device="cuda" if torch.cuda.is_available() else "cpu",
                                      download_root=reward_path)
            self.device = self.base_reward.device
            print(f"Successfully loaded ImageReward model from {reward_path}")
        except Exception as e:
            print(f"Error loading ImageReward model: {str(e)}")
            print(f"Using default cache location instead of {reward_path}")
            # Fall back to default location if specified path fails
            self.base_reward = RM.load("ImageReward-v1.0", 
                                      device="cuda" if torch.cuda.is_available() else "cpu")
            self.device = self.base_reward.device
        
    def get_reward(self, rendered_img, svg_paths, prompt):
        """
        Calculate a hybrid reward combining ImageReward with tactile-specific metrics
        
        Args:
            rendered_img: The rendered PNG image of the SVG
            svg_paths: The vector paths from the SVG
            prompt: The text prompt used for generation
        """
        # 1) Turn the model's output (a tensor or numpy array) into a PIL image
        # 2) Ask ImageReward to score it (base_reward)
        # 3) Compute tactile metrics on the raw SVG vector paths   
        # 4) Combine them: 70% aesthetic + 30% tactile

        # Convert tensor to PIL image if needed
        if isinstance(rendered_img, torch.Tensor):
            # Convert NCHW format to PIL
            img = rendered_img.squeeze(0).permute(1, 2, 0).cpu().numpy()
            img = (img * 255).astype(np.uint8)
            pil_img = Image.fromarray(img)
        elif isinstance(rendered_img, np.ndarray):
            pil_img = Image.fromarray(rendered_img)
        else:
            pil_img = rendered_img
            
        # Get base aesthetic reward from ImageReward
        base_reward = self.base_reward.score(prompt, pil_img)
        print(f"DEBUG: base_reward={base_reward}, type={type(base_reward)}")
        
        # Calculate tactile-specific metrics
        tactile_metrics = self._calculate_tactile_metrics(svg_paths, pil_img)
        print(f"DEBUG: tactile_metrics={tactile_metrics}, type={type(tactile_metrics)}, requires_grad={tactile_metrics.requires_grad if isinstance(tactile_metrics, torch.Tensor) else 'N/A'}")
        
        # Combine rewards with appropriate weights
        # First ensure base_reward is a tensor
        if not isinstance(base_reward, torch.Tensor):
            base_reward = torch.tensor(base_reward, device=self.device, dtype=torch.float32)
            
        reward_value = base_reward * 0.3 + tactile_metrics * 0.7
        print(f"DEBUG: reward_value={reward_value}, type={type(reward_value)}, requires_grad={reward_value.requires_grad}")
        
        # Explicitly create a new tensor with requires_grad=True
        final_reward = torch.tensor(reward_value.item(), device=self.device, dtype=torch.float32, requires_grad=True)
        print(f"DEBUG: final_reward={final_reward}, type={type(final_reward)}, requires_grad={final_reward.requires_grad}")
        
        return final_reward
    
    def _calculate_tactile_metrics(self, svg_paths, pil_img):
        """Calculate tactile-specific metrics from SVG paths"""
        # 1. Stroke width consistency (favors uniform stroke widths)
        stroke_widths = []
        for path in svg_paths:
            if hasattr(path, 'stroke_width'):
                stroke_widths.append(path.stroke_width.item())
        
        if stroke_widths:
            stroke_consistency = 1.0 - min(1.0, np.std(stroke_widths) / np.mean(stroke_widths) if np.mean(stroke_widths) > 0 else 0)
        else:
            stroke_consistency = 0.5  # Default value if no stroke widths
        
        # 2. Path simplicity (fewer control points is better for tactile)
        total_points = 0
        for path in svg_paths:
            if hasattr(path, 'points'):
                total_points += len(path.points)
        
        # Normalize path count - lower is better for tactile but we need enough detail
        # Sigmoid function to map point count to 0-1 range with sweet spot around 100-300 points
        path_simplicity = 2.0 / (1.0 + np.exp(total_points / 200 - 1.5))
        
        # 3. Element spacing (reward appropriate spacing between elements)
        # This is a complex calculation that would require path analysis
        # Simplified version for demonstration
        spacing_score = 0.7  # Default reasonable value
        
        # 4. Background cleanliness (fraction of nearly-white pixels)
        if pil_img is not None:
            gray = np.array(pil_img.convert('L'))
            white_frac = np.mean(gray > 250)  # 1.0 = totally white
        else:
            white_frac = 0.5  # Default value if no image is provided

        # Combine metrics with weights
        tactile_score = (
            stroke_consistency * 0.3 +
            path_simplicity    * 0.4 +
            spacing_score      * 0.2 +
            white_frac         * 0.1
        )
        
        # Return as tensor to ensure gradient flow
        return torch.tensor(tactile_score, device=self.device, dtype=torch.float32) 