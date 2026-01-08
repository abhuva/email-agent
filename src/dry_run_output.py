"""
Console output formatting for dry-run mode.

This module provides formatted console output for dry-run operations,
including section headers, color coding, and structured information display.

Usage:
    >>> from src.dry_run_output import DryRunOutput
    >>> 
    >>> output = DryRunOutput()
    >>> output.header("Email Processing")
    >>> output.info("Would process email UID 12345")
    >>> output.success("Classification: Important")
    >>> output.warning("Would write file to: /path/to/file.md")
"""
import sys
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

# Try to import colorama for cross-platform color support
try:
    import colorama
    colorama.init()  # Initialize colorama for Windows support
    COLORAMA_AVAILABLE = True
except ImportError:
    COLORAMA_AVAILABLE = False

# ANSI color codes
class Colors:
    """ANSI color codes for terminal output."""
    RESET = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    
    # Text colors
    BLACK = '\033[30m'
    RED = '\033[31m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    BLUE = '\033[34m'
    MAGENTA = '\033[35m'
    CYAN = '\033[36m'
    WHITE = '\033[37m'
    
    # Background colors
    BG_BLACK = '\033[40m'
    BG_RED = '\033[41m'
    BG_GREEN = '\033[42m'
    BG_YELLOW = '\033[43m'
    BG_BLUE = '\033[44m'
    BG_MAGENTA = '\033[45m'
    BG_CYAN = '\033[46m'
    BG_WHITE = '\033[47m'


def _colorize(text: str, color: str, bold: bool = False) -> str:
    """
    Apply color to text if colorama is available.
    
    Args:
        text: Text to colorize
        color: Color code to apply
        bold: Whether to make text bold
        
    Returns:
        Colorized text (or original text if colorama not available)
    """
    if not COLORAMA_AVAILABLE:
        return text
    
    result = text
    if bold:
        result = Colors.BOLD + result
    result = color + result + Colors.RESET
    return result


class DryRunOutput:
    """
    Formatted console output for dry-run mode.
    
    Provides structured, readable output with section headers,
    color coding, and consistent formatting.
    """
    
    def __init__(self, use_colors: bool = True):
        """
        Initialize dry-run output formatter.
        
        Args:
            use_colors: Whether to use color coding (default: True)
        """
        self.use_colors = use_colors and COLORAMA_AVAILABLE
        self._indent_level = 0
        self._indent_string = "  "
    
    def _print(self, text: str, color: Optional[str] = None, bold: bool = False, prefix: str = "") -> None:
        """
        Print formatted text.
        
        Args:
            text: Text to print
            color: Optional color code
            bold: Whether to make text bold
            prefix: Optional prefix string
        """
        indent = self._indent_string * self._indent_level
        full_text = indent + prefix + text
        
        if self.use_colors and color:
            full_text = _colorize(full_text, color, bold)
        
        print(full_text, file=sys.stdout)
    
    def header(self, text: str, level: int = 1) -> None:
        """
        Print a section header.
        
        Args:
            text: Header text
            level: Header level (1-3, affects size/emphasis)
        """
        if level == 1:
            self._print("", prefix="")
            self._print("=" * 70, color=Colors.CYAN, bold=True)
            self._print(text.upper(), color=Colors.CYAN, bold=True)
            self._print("=" * 70, color=Colors.CYAN, bold=True)
        elif level == 2:
            self._print("", prefix="")
            self._print("-" * 70, color=Colors.BLUE, bold=True)
            self._print(text, color=Colors.BLUE, bold=True)
            self._print("-" * 70, color=Colors.BLUE, bold=True)
        else:
            self._print("", prefix="")
            self._print(text, color=Colors.CYAN, bold=True)
    
    def info(self, text: str) -> None:
        """
        Print informational message.
        
        Args:
            text: Message text
        """
        self._print(f"ℹ️  {text}", color=Colors.CYAN)
    
    def success(self, text: str) -> None:
        """
        Print success message.
        
        Args:
            text: Message text
        """
        self._print(f"✓ {text}", color=Colors.GREEN, bold=True)
    
    def warning(self, text: str) -> None:
        """
        Print warning message.
        
        Args:
            text: Message text
        """
        self._print(f"⚠️  {text}", color=Colors.YELLOW, bold=True)
    
    def error(self, text: str) -> None:
        """
        Print error message.
        
        Args:
            text: Message text
        """
        self._print(f"✗ {text}", color=Colors.RED, bold=True)
    
    def detail(self, label: str, value: Any, indent: bool = True) -> None:
        """
        Print a detail line (label: value).
        
        Args:
            label: Label text
            value: Value to display
            indent: Whether to apply current indent level
        """
        if indent:
            self._print(f"{label}: {value}", color=Colors.WHITE)
        else:
            print(f"{label}: {value}", file=sys.stdout)
    
    def section(self, title: str) -> None:
        """
        Start a new section (increases indent).
        
        Args:
            title: Section title
        """
        self._print("", prefix="")
        self._print(title, color=Colors.BLUE, bold=True)
        self._indent_level += 1
    
    def end_section(self) -> None:
        """End current section (decreases indent)."""
        if self._indent_level > 0:
            self._indent_level -= 1
    
    def code_block(self, text: str, language: str = "") -> None:
        """
        Print a code block.
        
        Args:
            text: Code text
            language: Optional language identifier
        """
        self._print("", prefix="")
        if language:
            self._print(f"```{language}", color=Colors.DIM)
        else:
            self._print("```", color=Colors.DIM)
        
        # Print code lines with minimal formatting
        for line in text.split('\n'):
            self._print(line, color=Colors.WHITE)
        
        self._print("```", color=Colors.DIM)
        self._print("", prefix="")
    
    def table(self, headers: List[str], rows: List[List[str]]) -> None:
        """
        Print a simple table.
        
        Args:
            headers: List of header strings
            rows: List of rows, each row is a list of cell strings
        """
        # Calculate column widths
        col_widths = [len(h) for h in headers]
        for row in rows:
            for i, cell in enumerate(row):
                if i < len(col_widths):
                    col_widths[i] = max(col_widths[i], len(str(cell)))
        
        # Print header
        header_row = " | ".join(h.ljust(col_widths[i]) for i, h in enumerate(headers))
        self._print(header_row, color=Colors.CYAN, bold=True)
        self._print("-" * len(header_row), color=Colors.DIM)
        
        # Print rows
        for row in rows:
            row_str = " | ".join(str(cell).ljust(col_widths[i]) for i, cell in enumerate(row))
            self._print(row_str, color=Colors.WHITE)
    
    def summary(self, stats: Dict[str, Any]) -> None:
        """
        Print summary statistics.
        
        Args:
            stats: Dictionary of statistic name -> value
        """
        self.header("Summary", level=2)
        for key, value in stats.items():
            self.detail(key, value)
        self._print("", prefix="")
