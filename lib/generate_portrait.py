#!/usr/bin/env python3
"""
Portrait Frame Generator
Uses Google Gemini to generate stylized portrait frames based on:
1. Original person image (reference)
2. Art style image(s) (style reference)
3. Text prompt (additional instructions)
"""

import os
import sys
import argparse
from pathlib import Path
from typing import List
import logging

import google.generativeai as genai
from dotenv import load_dotenv
from PIL import Image

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)


class PortraitGenerator:
    """Generate stylized portrait frames using Gemini."""

    def __init__(self, model_name: str = "gemini-3-pro-image-preview"):
        """
        Initialize the portrait generator.

        Args:
            model_name: Gemini model to use
        """
        # Get API key from environment
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY not found in .env file")

        # Configure Gemini
        genai.configure(api_key=api_key)

        # Initialize model
        try:
            self.model = genai.GenerativeModel(model_name)
            logger.info(f"Initialized Gemini model: {model_name}")
        except Exception as e:
            logger.error(f"Error initializing model {model_name}: {e}")
            raise

        self.output_dir = Path("generated_portraits")
        self.output_dir.mkdir(exist_ok=True)

    def generate_portrait(
        self,
        person_image_path: str,
        style_image_paths: List[str],
        prompt: str,
        output_name: str = None
    ) -> str:
        """
        Generate a stylized portrait based on reference images and prompt.

        Args:
            person_image_path: Path to the original person image
            style_image_paths: List of paths to art style reference images
            prompt: Text description of desired output
            output_name: Optional custom output filename

        Returns:
            Path to generated image
        """
        logger.info("=" * 60)
        logger.info("Generating Stylized Portrait")
        logger.info("=" * 60)

        # Load person image
        logger.info(f"Loading person image: {person_image_path}")
        try:
            person_img = Image.open(person_image_path)
        except Exception as e:
            logger.error(f"Error loading person image: {e}")
            return None

        # Load style images
        style_imgs = []
        for style_path in style_image_paths:
            logger.info(f"Loading style image: {style_path}")
            try:
                style_imgs.append(Image.open(style_path))
            except Exception as e:
                logger.error(f"Error loading style image {style_path}: {e}")
                continue

        if not style_imgs:
            logger.error("No valid style images loaded")
            return None

        # Build comprehensive prompt for image generation
        analysis_prompt = self._build_analysis_prompt(prompt, len(style_imgs))

        logger.info("\nAnalyzing reference images and generating portrait...")

        try:
            # Prepare content list: prompt + person image + style images
            content = [analysis_prompt, person_img] + style_imgs

            # Generate response
            response = self.model.generate_content(content)

            logger.info("\nGeneration response received")
            logger.info("=" * 60)

            # Check if response contains generated image
            if hasattr(response, 'parts'):
                for part in response.parts:
                    if hasattr(part, 'inline_data'):
                        # Save generated image
                        image_data = part.inline_data.data

                        if not output_name:
                            output_name = f"portrait_{Path(person_image_path).stem}.png"

                        output_path = self.output_dir / output_name

                        # If file exists, add counter to avoid overwriting
                        if output_path.exists():
                            counter = 1
                            stem = output_path.stem
                            ext = output_path.suffix
                            while output_path.exists():
                                output_name = f"{stem}_{counter:02d}{ext}"
                                output_path = self.output_dir / output_name
                                counter += 1

                        with open(output_path, 'wb') as f:
                            f.write(image_data)

                        logger.info(f"✓ Generated portrait saved to: {output_path}")
                        return str(output_path)

            # If no image in response, print the text response
            if response.text:
                logger.info("\nModel Response:")
                logger.info("-" * 60)
                logger.info(response.text)
                logger.info("-" * 60)
                logger.warning("\nNote: Model returned text instead of image.")
                logger.warning("This model may not support image generation.")
                logger.warning("Consider using Imagen or another image generation service.")

            return None

        except Exception as e:
            logger.error(f"Error generating portrait: {e}")
            return None

    def _build_analysis_prompt(self, user_prompt: str, num_style_images: int) -> str:
        """
        Build a comprehensive prompt for portrait generation.

        Args:
            user_prompt: User's custom prompt
            num_style_images: Number of style reference images

        Returns:
            Complete prompt for Gemini
        """
        base_prompt = f"""You are an expert at generating stylized portrait artwork.

I'm providing you with:
1. ONE reference photo of a person (their face, features, and characteristics)
2. {num_style_images} style reference image(s) showing the desired artistic style

Your task: Generate a NEW portrait that captures the PERSON from the first image rendered in the ARTISTIC STYLE of the reference images.

Key requirements:
- Maintain the person's distinctive facial features, structure, and characteristics
- Apply the artistic style, technique, and visual aesthetic from the style references
- Match the color palette, line work, shading, and overall visual treatment of the style images
- Ensure the output is a single portrait frame suitable for use in a comic or graphic novel

Additional instructions: {user_prompt}

Generate the portrait now."""

        return base_prompt

    def batch_generate(
        self,
        person_image_path: str,
        style_image_paths: List[str],
        prompts: List[str]
    ) -> List[str]:
        """
        Generate multiple portraits with different prompts.

        Args:
            person_image_path: Path to person image
            style_image_paths: List of style reference images
            prompts: List of different prompts to try

        Returns:
            List of paths to generated images
        """
        results = []

        for i, prompt in enumerate(prompts, 1):
            logger.info(f"\n[{i}/{len(prompts)}] Generating with prompt: {prompt[:50]}...")
            output_name = f"portrait_variant_{i:02d}.png"
            result = self.generate_portrait(
                person_image_path,
                style_image_paths,
                prompt,
                output_name
            )
            if result:
                results.append(result)

        return results


# Predefined expression prompts for easy steering
EXPRESSIONS = {
    'amused': 'amused expression with a playful glint in the eyes, entertained and tickled look',
    'angry': 'angry and intense expression with furrowed brow, aggressive and fierce demeanor',
    'annoyed': 'annoyed and irritated expression with tight lips, exasperated and impatient look',
    'bored': 'bored and disinterested expression with heavy-lidded eyes, listless and unengaged look',
    'confident': 'confident and self-assured expression with steady gaze, bold and poised demeanor',
    'confused': 'confused and puzzled expression with questioning look, uncertain and bewildered demeanor',
    'contemplative': 'contemplative and thoughtful expression with distant gaze, introspective and pensive mood',
    'crying': 'crying with tears streaming down face, deeply emotional and overwhelmed expression',
    'defeated': 'defeated and dejected expression with slumped features, exhausted and hopeless look',
    'defiant': 'defiant and rebellious expression with jutted chin, unyielding and stubborn demeanor',
    'determined': 'determined and focused expression with strong jaw, resolute and confident demeanor',
    'disappointed': 'disappointed expression with downcast eyes, let down and disheartened look',
    'disgusted': 'disgusted expression with wrinkled nose, repulsed and revolted look',
    'dreamy': 'dreamy and wistful expression with soft unfocused gaze, romantic and longing mood',
    'embarrassed': 'embarrassed expression with flushed cheeks, self-conscious and sheepish look',
    'excited': 'excited and energetic expression with bright wide eyes, eager and enthusiastic demeanor',
    'exhausted': 'exhausted and fatigued expression with dark circles and drooping features, drained and weary look',
    'fearful': 'fearful and terrified expression with wide panicked eyes, dread and horror in the face',
    'flirty': 'flirty and coy expression with a sly smile and half-lidded eyes, playful and alluring look',
    'frustrated': 'frustrated and exasperated expression with clenched jaw, agitated and strained look',
    'grateful': 'grateful and appreciative expression with warm soft eyes, thankful and touched demeanor',
    'grieving': 'grieving and sorrowful expression with deep sadness, anguished and heartbroken look',
    'guilty': 'guilty and remorseful expression with averted gaze, ashamed and regretful look',
    'happy': 'happy and joyful expression with a bright genuine smile, cheerful and uplifting mood',
    'hopeful': 'hopeful and optimistic expression with uplifted features, expectant and encouraged look',
    'jealous': 'jealous and envious expression with narrowed eyes, resentful and covetous look',
    'laughing': 'laughing heartily with eyes crinkled in joy, authentic amusement and delight',
    'longing': 'longing and yearning expression with distant sad eyes, nostalgic and aching mood',
    'mischievous': 'mischievous expression with a sly grin and twinkling eyes, impish and cunning look',
    'nervous': 'nervous and uneasy expression with darting eyes, jittery and apprehensive look',
    'neutral': 'neutral calm expression, composed and balanced demeanor',
    'nostalgic': 'nostalgic and sentimental expression with bittersweet smile, reflective and wistful mood',
    'panicked': 'panicked and frantic expression with wild desperate eyes, terrified and overwhelmed look',
    'peaceful': 'peaceful and serene expression with relaxed features, tranquil and content mood',
    'playful': 'playful and lighthearted expression with a teasing grin, fun-loving and spirited demeanor',
    'proud': 'proud and triumphant expression with lifted chin and broad smile, accomplished and dignified look',
    'relieved': 'relieved expression with relaxed tension, grateful exhale and weight-off-shoulders look',
    'sad': 'sad and melancholic expression with downturned features, somber and reflective mood',
    'sarcastic': 'sarcastic expression with raised eyebrow and half-smile, dry and ironic demeanor',
    'scared': 'frightened and fearful expression with wide eyes, anxious and alarmed look',
    'serious': 'serious and stern expression with intense gaze, grave and solemn mood',
    'shocked': 'shocked and stunned expression with jaw dropped and wide eyes, disbelief and astonishment',
    'shouting': 'shouting or yelling with mouth wide open, intense vocal expression',
    'shy': 'shy and timid expression with downcast eyes, reserved and bashful demeanor',
    'skeptical': 'skeptical and doubtful expression with raised eyebrow, questioning and unconvinced look',
    'smiling': 'warm friendly smile with gentle eyes, approachable and kind expression',
    'smirking': 'smirking with slight confident smile, knowing and self-assured expression',
    'smug': 'smug and self-satisfied expression with a cocky grin, arrogant and superior demeanor',
    'surprised': 'surprised expression with wide eyes and raised eyebrows, shocked and astonished look',
    'suspicious': 'suspicious and wary expression with narrowed eyes, distrustful and guarded look',
    'tender': 'tender and loving expression with soft gentle eyes, caring and affectionate mood',
    'terrified': 'terrified expression with frozen wide-eyed stare, paralyzed with fear and dread',
    'tired': 'tired and sleepy expression with half-closed eyes, drowsy and worn-out look',
    'triumphant': 'triumphant and victorious expression with fierce pride, exultant and commanding demeanor',
    'vulnerable': 'vulnerable and exposed expression with glistening eyes, raw and emotionally open look',
    'worried': 'worried and concerned expression with tense features, anxious and troubled look',
}


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description='Generate stylized portrait frames using Google Gemini',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Using predefined expression
  python generate_portrait.py --person photo.jpg --style comic_style.jpg --expression happy

  # Multiple style references with expression
  python generate_portrait.py --person photo.jpg --style style1.jpg style2.jpg --expression angry

  # Custom prompt (overrides expression)
  python generate_portrait.py --person photo.jpg --style comic.jpg --prompt "surprised with dramatic lighting"

  # Available expressions:
  happy, sad, angry, surprised, confused, smiling, laughing, shouting,
  determined, scared, disgusted, neutral, serious, smirking, worried
        """
    )

    parser.add_argument(
        '--person',
        required=True,
        help='Path to the person/reference image'
    )

    parser.add_argument(
        '--style',
        nargs='+',
        required=True,
        help='Path(s) to art style reference image(s)'
    )

    parser.add_argument(
        '--expression',
        choices=list(EXPRESSIONS.keys()),
        help='Predefined expression/emotion (alternative to --prompt)'
    )

    parser.add_argument(
        '--prompt',
        help='Custom text prompt describing the desired output (overrides --expression if both provided)'
    )

    parser.add_argument(
        '--output',
        help='Custom output filename (default: auto-generated)'
    )

    parser.add_argument(
        '--model',
        default='gemini-3-pro-image-preview',
        help='Gemini model to use (default: gemini-3-pro-image-preview)'
    )

    args = parser.parse_args()

    # Check for API key
    if not os.getenv("GOOGLE_API_KEY"):
        logger.error("GOOGLE_API_KEY not found!")
        logger.error("Please create a .env file with your API key:")
        logger.error("  GOOGLE_API_KEY=your_key_here")
        sys.exit(1)

    # Ensure either expression or prompt is provided
    if not args.expression and not args.prompt:
        logger.error("Error: Either --expression or --prompt must be provided")
        parser.print_help()
        sys.exit(1)

    # Determine which prompt to use
    if args.prompt:
        # Custom prompt takes precedence
        prompt_to_use = args.prompt
        logger.info(f"Using custom prompt: {prompt_to_use}")
    else:
        # Use predefined expression
        prompt_to_use = EXPRESSIONS[args.expression]
        logger.info(f"Using expression '{args.expression}': {prompt_to_use}")

    # Validate input files
    if not Path(args.person).exists():
        logger.error(f"Person image not found: {args.person}")
        sys.exit(1)

    for style_path in args.style:
        if not Path(style_path).exists():
            logger.error(f"Style image not found: {style_path}")
            sys.exit(1)

    # Generate portrait
    try:
        generator = PortraitGenerator(model_name=args.model)
        result = generator.generate_portrait(
            args.person,
            args.style,
            prompt_to_use,
            args.output
        )

        if result:
            logger.info(f"\n✓ Success! Portrait saved to: {result}")
        else:
            logger.error("\n✗ Portrait generation failed")
            sys.exit(1)

    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
