"""
KiCad connection management and error handling.
"""
from typing import Tuple

try:
    from kipy import KiCad
    from kipy.board import Board
    KICAD_AVAILABLE = True
except ImportError:
    KICAD_AVAILABLE = False
    # Provide type hints even if kicad-python not installed
    KiCad = None  # type: ignore
    Board = None  # type: ignore


def connect_to_kicad() -> Tuple['KiCad', 'Board']:
    """
    Establish connection to KiCad and get current board.

    Returns:
        Tuple of (KiCad instance, Board instance)

    Raises:
        ImportError: If kicad-python is not installed
        ConnectionError: If cannot connect to KiCad
        RuntimeError: If no board is open
    """
    if not KICAD_AVAILABLE:
        raise ImportError(
            "kicad-python is not installed. "
            "Install it with: pip install kicad-python>=0.2.0"
        )

    try:
        kicad = KiCad()
    except Exception as e:
        raise ConnectionError(
            f"Cannot connect to KiCad. Is KiCad running with API enabled?\n"
            f"(Preferences > Plugins > Enable API server)\n"
            f"Error: {e}"
        )

    # Check version compatibility
    try:
        version = kicad.get_version()
        print(f"Connected to KiCad {version}")

        if not kicad.check_version():
            print("Warning: KiCad version may not match kicad-python version")
    except Exception as e:
        print(f"Warning: Could not check version compatibility: {e}")

    try:
        board = kicad.get_board()
    except Exception as e:
        raise RuntimeError(
            f"Cannot get board. Is a PCB file open in KiCad?\n"
            f"Error: {e}"
        )

    return kicad, board


def check_kicad_available() -> bool:
    """
    Check if kicad-python is available.

    Returns:
        True if kicad-python can be imported
    """
    return KICAD_AVAILABLE
