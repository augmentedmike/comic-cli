#!/usr/bin/env python3
"""
Portrait Generator - Interactive TUI
Terminal User Interface for generating stylized portraits
"""

import os
import sys
import json
from pathlib import Path
from typing import List, Optional, Dict, Tuple

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.table import Table
from rich import box
from InquirerPy import inquirer
from InquirerPy.base.control import Choice

from generate_portrait import PortraitGenerator, EXPRESSIONS

console = Console()

# Preferences file
PREFS_FILE = Path(".portrait_prefs.json")

# Aspect ratio options
ASPECT_RATIOS = {
    '1:1': {'width': 1024, 'height': 1024, 'desc': 'Square'},
    '4:3': {'width': 1024, 'height': 768, 'desc': 'Classic'},
    '3:4': {'width': 768, 'height': 1024, 'desc': 'Portrait'},
    '16:9': {'width': 1024, 'height': 576, 'desc': 'Widescreen'},
    '9:16': {'width': 576, 'height': 1024, 'desc': 'Phone/Vertical'},
}



def load_preferences() -> Optional[Dict]:
    """Load saved preferences from file."""
    if PREFS_FILE.exists():
        try:
            with open(PREFS_FILE, 'r') as f:
                prefs = json.load(f)
                # Validate that files still exist
                if Path(prefs['person']).exists() and all(Path(s).exists() for s in prefs['styles']):
                    return prefs
        except (json.JSONDecodeError, KeyError, FileNotFoundError):
            pass
    return None


def save_preferences(person: Path, styles: List[Path]):
    """Save current selection as preferences."""
    prefs = {
        'person': str(person),
        'styles': [str(s) for s in styles]
    }
    with open(PREFS_FILE, 'w') as f:
        json.dump(prefs, f, indent=2)


def show_banner():
    """Display welcome banner."""
    banner = """
╔═══════════════════════════════════════════════════════════╗
║                                                           ║
║     🎨  PORTRAIT GENERATOR - Interactive TUI  🎨          ║
║                                                           ║
║     Generate stylized comic book portrait frames         ║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝
    """
    console.print(banner, style="bold cyan")


def get_image_files(directory: str, pattern: str = "*") -> List[Path]:
    """Get all image files from a directory."""
    source_dir = Path(directory)
    if not source_dir.exists():
        return []

    extensions = ['*.jpg', '*.jpeg', '*.png', '*.JPG', '*.JPEG', '*.PNG']
    files = []
    for ext in extensions:
        files.extend(source_dir.glob(ext))

    return sorted(files)


def select_person_image() -> Path:
    """Interactive selection of person/reference image."""
    console.print("\n[bold yellow]Step 1:[/bold yellow] Select reference person image", style="bold")

    images = get_image_files('source')

    if not images:
        console.print("[red]No images found in source/ directory![/red]")
        sys.exit(1)

    choices = [Choice(value=str(img), name=f"{img.name} ({img.stat().st_size // 1024}KB)")
               for img in images]

    selected = inquirer.select(
        message="Choose the person/reference image:",
        choices=choices,
        default=None,
    ).execute()

    return Path(selected)


def select_style_images() -> List[Path]:
    """Interactive multi-selection of style reference images."""
    console.print("\n[bold yellow]Step 2:[/bold yellow] Select art style reference images", style="bold")
    console.print("[dim]Use SPACE to select/deselect, ENTER to confirm[/dim]\n")

    images = get_image_files('source')

    if not images:
        console.print("[red]No images found in source/ directory![/red]")
        sys.exit(1)

    choices = [Choice(value=str(img), name=f"{img.name} ({img.stat().st_size // 1024}KB)")
               for img in images]

    selected = inquirer.checkbox(
        message="Choose style reference images (select multiple):",
        choices=choices,
        validate=lambda result: len(result) >= 1,
        invalid_message="Select at least one style image",
    ).execute()

    return [Path(img) for img in selected]


def select_aspect_ratio() -> Tuple[str, int, int]:
    """Select aspect ratio for the portrait. Returns (ratio_string, width, height)."""
    console.print("\n[bold yellow]Select Aspect Ratio[/bold yellow]")

    choices = [
        Choice(value=ratio, name=f"{ratio:<6} - {info['desc']:<15} ({info['width']}x{info['height']})")
        for ratio, info in ASPECT_RATIOS.items()
    ]

    selected = inquirer.select(
        message="Choose aspect ratio:",
        choices=choices,
        default='1:1'
    ).execute()

    ratio_info = ASPECT_RATIOS[selected]
    width, height = ratio_info['width'], ratio_info['height']

    # Ask if user wants to flip (except for 1:1 which is square)
    if selected != '1:1' and width != height:
        flip = Confirm.ask(f"\n[cyan]Flip to {height}x{width}?[/cyan]", default=False)
        if flip:
            width, height = height, width
            # Swap ratio string
            parts = selected.split(':')
            selected = f"{parts[1]}:{parts[0]}"

    return selected, width, height


def select_expression_or_prompt() -> str:
    """Interactive selection of expression or custom prompt."""
    console.print("\n[bold yellow]Step 3:[/bold yellow] Choose expression or enter custom prompt", style="bold")

    # Ask if user wants predefined or custom
    choice = inquirer.select(
        message="How would you like to control the expression?",
        choices=[
            Choice(value="predefined", name="🎭 Use predefined expression"),
            Choice(value="custom", name="✏️  Enter custom prompt"),
        ],
    ).execute()

    if choice == "predefined":
        # Show expression options
        expression_choices = [
            Choice(value=key, name=f"{key.capitalize():<12} - {desc[:50]}...")
            for key, desc in EXPRESSIONS.items()
        ]

        selected_expr = inquirer.select(
            message="Select an expression:",
            choices=expression_choices,
        ).execute()

        return EXPRESSIONS[selected_expr]

    else:
        # Custom prompt
        custom = Prompt.ask("\n[cyan]Enter your custom prompt[/cyan]")
        return custom


def show_summary(person: Path, styles: List[Path], prompt: str):
    """Display generation summary."""
    console.print("\n" + "="*60)
    console.print("[bold green]Generation Summary[/bold green]")
    console.print("="*60)

    table = Table(show_header=False, box=box.SIMPLE)
    table.add_column("Field", style="cyan", width=20)
    table.add_column("Value", style="white")

    table.add_row("Reference Image", person.name)
    table.add_row("Style Images", f"{len(styles)} selected")
    for i, style in enumerate(styles, 1):
        table.add_row("", f"  {i}. {style.name}")
    table.add_row("Prompt", prompt[:80] + "..." if len(prompt) > 80 else prompt)

    console.print(table)
    console.print("="*60 + "\n")


def generate_portrait_interactive(
    person: Path,
    styles: List[Path],
    prompt: str,
    generator: PortraitGenerator,
    expression: Optional[str] = None,
    aspect_ratio: Optional[str] = None
):
    """Generate portrait with progress feedback."""

    # Ask for output filename
    if expression and aspect_ratio:
        # Replace : with x for filename
        ratio_clean = aspect_ratio.replace(':', 'x')
        default_name = f"{person.stem}-{expression}-{ratio_clean}.png"
    elif expression:
        default_name = f"{person.stem}-{expression}.png"
    else:
        default_name = f"portrait_{person.stem}.png"

    output_name = Prompt.ask(
        "\n[cyan]Output filename[/cyan]",
        default=default_name
    )

    console.print("\n[bold cyan]Generating portrait...[/bold cyan]")
    console.print("[dim]This may take 10-20 seconds...[/dim]\n")

    with console.status("[bold green]Analyzing images and generating..."):
        result = generator.generate_portrait(
            str(person),
            [str(s) for s in styles],
            prompt,
            output_name
        )

    if result:
        console.print(f"\n[bold green]✓ Success![/bold green] Portrait saved to:")
        console.print(f"  [bold cyan]{result}[/bold cyan]\n")
        return result
    else:
        console.print("\n[bold red]✗ Generation failed[/bold red]")
        return None


def quick_generate_mode(
    person: Path,
    styles: List[Path],
    generator: PortraitGenerator
) -> bool:
    """Quick generation mode - just select expression and go."""
    console.print("\n[bold green]Quick Generate Mode[/bold green]")
    console.print(f"[dim]Using: {person.name} with {len(styles)} style images[/dim]\n")

    # Quick generate - just pick expression
    console.print("\n[bold yellow]Select Expression[/bold yellow]")

    expression_choices = [
        Choice(value=key, name=f"{key.capitalize():<12} - {desc[:50]}...")
        for key, desc in EXPRESSIONS.items()
    ]
    expression_choices.extend([
        Choice(value="custom", name="✏️  Custom prompt"),
        Choice(value="change", name="🔄 Change images"),
        Choice(value="exit", name="❌ Exit")
    ])

    selected = inquirer.select(
        message="Choose an expression:",
        choices=expression_choices,
    ).execute()

    if selected == "exit":
        return False
    elif selected == "change":
        return True  # Signal to do full selection
    elif selected == "custom":
        prompt = Prompt.ask("\n[cyan]Enter your custom prompt[/cyan]")
        expression_name = None
    else:
        expression_name = selected
        prompt = EXPRESSIONS[selected]
        console.print(f"\n[dim]Using: {prompt}[/dim]")

    # Select aspect ratio
    aspect_ratio, width, height = select_aspect_ratio()

    # Add aspect ratio to prompt
    full_prompt = f"{prompt}\n\nGenerate as {width}x{height} pixels ({aspect_ratio} aspect ratio)."

    # Generate immediately
    result = generate_portrait_interactive(
        person, styles, full_prompt, generator, expression_name, aspect_ratio
    )

    return True  # Continue loop


def main():
    """Main TUI loop."""
    show_banner()

    # Check for API key
    if not os.getenv("GOOGLE_API_KEY"):
        console.print("[bold red]Error:[/bold red] GOOGLE_API_KEY not found in .env file!")
        console.print("Please create a .env file with your API key.")
        sys.exit(1)

    try:
        # Initialize generator
        console.print("\n[dim]Initializing Gemini AI...[/dim]")
        generator = PortraitGenerator(model_name="gemini-3-pro-image-preview")
        console.print("[green]✓ Ready![/green]\n")

        # Check for saved preferences
        prefs = load_preferences()
        person_image = None
        style_images = None

        if prefs:
            console.print("[bold green]✓ Found saved preferences![/bold green]")
            console.print(f"  Person: {Path(prefs['person']).name}")
            console.print(f"  Styles: {len(prefs['styles'])} images\n")

            use_prefs = Confirm.ask(
                "[bold]Use saved images for quick generation?[/bold]",
                default=True
            )

            if use_prefs:
                person_image = Path(prefs['person'])
                style_images = [Path(s) for s in prefs['styles']]

        while True:
            # Quick mode if we have saved images
            if person_image and style_images:
                should_continue = quick_generate_mode(person_image, style_images, generator)

                if not should_continue:
                    console.print("\n[cyan]Goodbye! 👋[/cyan]\n")
                    break

                # If quick_generate_mode returns True but we're here, user wants to change images
                if should_continue:
                    # Check if user actually generated or wants to change
                    continue

            # Full selection mode
            # Step 1: Select person image
            person_image = select_person_image()

            # Step 2: Select style images
            style_images = select_style_images()

            # Save preferences
            save_preferences(person_image, style_images)
            console.print("\n[green]✓ Preferences saved![/green]")

            # Step 3: Choose expression/prompt
            prompt = select_expression_or_prompt()

            # Show summary
            show_summary(person_image, style_images, prompt)

            # Confirm
            if not Confirm.ask("\n[bold]Generate this portrait?[/bold]", default=True):
                if not Confirm.ask("\n[yellow]Start over?[/yellow]", default=True):
                    console.print("\n[cyan]Goodbye! 👋[/cyan]\n")
                    break
                continue

            # Generate
            result = generate_portrait_interactive(
                person_image,
                style_images,
                prompt,
                generator,
                None  # No expression name in full mode
            )

            # Loop back to quick mode with these images

    except KeyboardInterrupt:
        console.print("\n\n[yellow]Interrupted by user[/yellow]")
        sys.exit(0)
    except Exception as e:
        console.print(f"\n[bold red]Error:[/bold red] {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
