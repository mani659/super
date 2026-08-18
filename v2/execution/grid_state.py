import time
import logging

logger = logging.getLogger("GridState")

class GridState:
    """
    Per-magic grid state tracker for V2.
    Tracks combined P&L for grid-level exits (Grid TP/Stop/Protector).
    """
    def __init__(self, max_legs: int = 4):
        self.legs: list = []    # list of open position tickets
        self.first_layer_risk: float = 0.0   # |entry_price - sl| of first leg
        self.active: bool = False
        self.max_legs = max_legs
        self.created_at: float = 0.0

    def add_leg(self, ticket: int, entry_price: float, sl: float):
        """Register a new leg when it fills."""
        if sl <= 0.0:
            return

        if len(self.legs) >= self.max_legs:
            return
            
        if not self.active:
            self.first_layer_risk = abs(entry_price - sl)
            self.active = True
            self.created_at = time.time()
            
        if ticket not in self.legs:
            self.legs.append(ticket)
            
    def sync(self, positions):
        """Keep tracker in sync with live positions."""
        live_tickets = {p.ticket for p in positions}
        self.legs = [t for t in self.legs if t in live_tickets]
        if not self.legs:
            self.reset()

    def combined_pnl(self, positions) -> float:
        """Sum of profit across all active grid legs."""
        ticket_set = set(self.legs)
        return sum(p.profit for p in positions if p.ticket in ticket_set)

    def r_multiple(self, positions) -> float:
        """Combined P&L expressed as R-multiple of first layer risk."""
        if self.first_layer_risk <= 0:
            return 0.0
        return self.combined_pnl(positions) / self.first_layer_risk

    def open_legs(self, positions) -> list:
        """Return position objects for all legs still open."""
        ticket_set = set(self.legs)
        return [p for p in positions if p.ticket in ticket_set]

    def reset(self):
        self.legs = []
        self.first_layer_risk = 0.0
        self.active = False
        self.created_at = 0.0
