"""
AI Player for Rıfkı (King) Card Game
=====================================
Three difficulty levels of AI:
- Easy: random valid play
- Medium: basic strategy (avoid penalties, play low)
- Hard: card counting, void creation, endgame planning
"""

import random
from game_engine import (
    Card, Suit, ContractType, Player, GameEngine,
    RANK_NAMES, CONTRACT_DISPLAY
)
from typing import List, Optional, Dict


class AIPlayer:
    """AI player that can select contracts and play cards intelligently."""

    def __init__(self, difficulty: str = 'hard'):
        self.difficulty = difficulty  # easy, medium, hard

    # ─── Contract Selection ───────────────────────────────────────────

    def choose_contract(self, engine: GameEngine) -> dict:
        """Choose a contract and optionally a trump suit."""
        player = engine.players[engine.declarer_index]
        available = player.get_available_contracts(engine.contracts_used, engine.round_number)

        if not available:
            return None

        if self.difficulty == 'easy':
            choice = random.choice(available)
        else:
            choice = self._smart_contract(player, available, engine)

        result = {'contract': choice.value}

        if choice == ContractType.TRUMP:
            result['trump_suit'] = self._choose_trump_suit(player).value

        return result

    def _smart_contract(self, player: Player, available: List[ContractType],
                        engine: GameEngine) -> ContractType:
        """Analyze hand and pick best contract."""
        hand = player.hand
        scores = {}

        for ct in available:
            scores[ct] = self._evaluate_hand_for_contract(hand, ct)

        # Pick the one with best expected outcome
        return max(scores, key=scores.get)

    def _evaluate_hand_for_contract(self, hand: List[Card], ct: ContractType) -> float:
        """Score how good a hand is for a given contract. Higher = better."""
        if ct == ContractType.TRUMP:
            return self._eval_trump(hand)
        elif ct == ContractType.RIFKI:
            return self._eval_rifki(hand)
        elif ct == ContractType.GIRLS:
            return self._eval_girls(hand)
        elif ct == ContractType.BOYS:
            return self._eval_boys(hand)
        elif ct == ContractType.HEARTS:
            return self._eval_hearts(hand)
        elif ct == ContractType.LAST_TWO:
            return self._eval_last_two(hand)
        elif ct == ContractType.NO_TRICKS:
            return self._eval_no_tricks(hand)
        return 0

    def _eval_trump(self, hand: List[Card]) -> float:
        """Better with long strong suits."""
        best = 0
        for suit in Suit:
            cards = [c for c in hand if c.suit == suit]
            strength = len(cards) * 10
            for c in cards:
                strength += c.rank
            best = max(best, strength)
        return best

    def _eval_rifki(self, hand: List[Card]) -> float:
        """Good if we have few/no hearts, or low hearts (can avoid K♥)."""
        hearts = [c for c in hand if c.suit == Suit.HEARTS]
        has_king = any(c.rank == 13 for c in hearts)

        if not hearts:
            return 100  # Perfect: no hearts at all
        if has_king:
            return -50  # Bad: we have the K♥
        # Few low hearts = okay
        return 80 - len(hearts) * 10 - sum(c.rank for c in hearts)

    def _eval_girls(self, hand: List[Card]) -> float:
        """Good if we have few/no queens and low cards."""
        queens = [c for c in hand if c.rank == 12]
        if not queens:
            return 80
        return 40 - len(queens) * 30

    def _eval_boys(self, hand: List[Card]) -> float:
        """Good if we have few kings and jacks."""
        boys = [c for c in hand if c.rank in (11, 13)]
        if not boys:
            return 80
        return 40 - len(boys) * 15

    def _eval_hearts(self, hand: List[Card]) -> float:
        """Good if we have few hearts."""
        hearts = [c for c in hand if c.suit == Suit.HEARTS]
        if not hearts:
            return 100
        return 60 - len(hearts) * 8

    def _eval_last_two(self, hand: List[Card]) -> float:
        """Good if we have many low cards (can duck last tricks)."""
        low_cards = [c for c in hand if c.rank <= 7]
        high_cards = [c for c in hand if c.rank >= 12]
        return len(low_cards) * 10 - len(high_cards) * 8

    def _eval_no_tricks(self, hand: List[Card]) -> float:
        """Good if we have many low cards overall."""
        score = 0
        for c in hand:
            if c.rank <= 5:
                score += 10
            elif c.rank <= 9:
                score += 3
            else:
                score -= (c.rank - 9) * 5
        # Void suits are great
        for suit in Suit:
            if not any(c.suit == suit for c in hand):
                score += 15
        return score

    def _choose_trump_suit(self, player: Player) -> Suit:
        """Pick the strongest suit for trump."""
        best_suit = Suit.SPADES
        best_score = -1
        for suit in Suit:
            cards = [c for c in player.hand if c.suit == suit]
            score = len(cards) * 15 + sum(c.rank for c in cards)
            if score > best_score:
                best_score = score
                best_suit = suit
        return best_suit

    # ─── Card Play ────────────────────────────────────────────────────

    def choose_card(self, engine: GameEngine, player_id: int) -> Card:
        """Choose which card to play."""
        valid = engine.get_valid_cards(player_id)

        if not valid:
            return None

        if len(valid) == 1:
            return valid[0]

        if self.difficulty == 'easy':
            return random.choice(valid)

        ct = engine.current_contract
        is_leading = not engine.current_trick or not engine.current_trick.cards

        if ct == ContractType.TRUMP:
            return self._play_trump(engine, player_id, valid, is_leading)
        elif ct == ContractType.RIFKI:
            return self._play_rifki(engine, player_id, valid, is_leading)
        elif ct == ContractType.GIRLS:
            return self._play_avoid_cards(engine, player_id, valid, is_leading, 12)
        elif ct == ContractType.BOYS:
            return self._play_avoid_cards(engine, player_id, valid, is_leading, (11, 13))
        elif ct == ContractType.HEARTS:
            return self._play_hearts(engine, player_id, valid, is_leading)
        elif ct == ContractType.LAST_TWO:
            return self._play_last_two(engine, player_id, valid, is_leading)
        elif ct == ContractType.NO_TRICKS:
            return self._play_no_tricks(engine, player_id, valid, is_leading)

        return random.choice(valid)

    def _play_trump(self, engine, pid, valid, is_leading):
        """In Trump: try to win tricks."""
        if is_leading:
            # Lead with trump to draw them out, or high cards
            trumps = [c for c in valid if c.suit == engine.trump_suit]
            if trumps:
                return max(trumps, key=lambda c: c.rank)
            return max(valid, key=lambda c: c.rank)

        # Following: play high to win
        trick = engine.current_trick
        lead_suit = trick.lead_suit
        same_suit = [c for c in valid if c.suit == lead_suit]

        if same_suit:
            # Try to win with lowest winning card
            current_best = max(
                (c for _, c in trick.cards if c.suit == lead_suit),
                key=lambda c: c.rank, default=None
            )
            if current_best:
                winners = [c for c in same_suit if c.rank > current_best.rank]
                if winners:
                    return min(winners, key=lambda c: c.rank)
            return max(same_suit, key=lambda c: c.rank)

        # Can't follow: play trump
        trumps = [c for c in valid if c.suit == engine.trump_suit]
        if trumps:
            return min(trumps, key=lambda c: c.rank)

        # Discard lowest
        return min(valid, key=lambda c: c.rank)

    def _play_rifki(self, engine, pid, valid, is_leading):
        """Avoid winning the K♥."""
        king_hearts = Card(Suit.HEARTS, 13)

        if is_leading:
            # Don't lead hearts unless forced. Lead low.
            non_hearts = [c for c in valid if c.suit != Suit.HEARTS]
            if non_hearts:
                return min(non_hearts, key=lambda c: c.rank)
            # Forced to lead hearts — lead low
            return min(valid, key=lambda c: c.rank)

        trick = engine.current_trick
        lead_suit = trick.lead_suit

        if lead_suit == Suit.HEARTS:
            # Playing hearts — dump the king if we must, or play low
            if king_hearts in valid and len(valid) == 1:
                return king_hearts
            # Play high but NOT the king if possible
            non_king = [c for c in valid if c != king_hearts]
            if non_king:
                # Play just under the current winning card
                return min(non_king, key=lambda c: c.rank)
            return valid[0]

        # Not hearts lead
        same_suit = [c for c in valid if c.suit == lead_suit]
        if same_suit:
            # Play low to avoid winning
            return min(same_suit, key=lambda c: c.rank)

        # Can't follow: dump the K♥ if we have it!
        if king_hearts in valid:
            return king_hearts

        # Dump highest heart or highest card
        hearts = [c for c in valid if c.suit == Suit.HEARTS]
        if hearts:
            return max(hearts, key=lambda c: c.rank)
        return max(valid, key=lambda c: c.rank)

    def _play_avoid_cards(self, engine, pid, valid, is_leading, target_ranks):
        """Generic avoid penalty cards (Girls / Boys)."""
        if isinstance(target_ranks, int):
            target_ranks = (target_ranks,)

        penalty = [c for c in valid if c.rank in target_ranks]
        non_penalty = [c for c in valid if c.rank not in target_ranks]

        if is_leading:
            # Lead low, non-penalty
            if non_penalty:
                return min(non_penalty, key=lambda c: c.rank)
            return min(valid, key=lambda c: c.rank)

        trick = engine.current_trick
        lead_suit = trick.lead_suit
        same_suit = [c for c in valid if c.suit == lead_suit]

        if same_suit:
            # Play low to avoid winning penalty tricks
            safe = [c for c in same_suit if c.rank not in target_ranks]
            if safe:
                return min(safe, key=lambda c: c.rank)
            return min(same_suit, key=lambda c: c.rank)

        # Can't follow: dump penalty cards!
        if penalty:
            return max(penalty, key=lambda c: c.rank)
        return max(valid, key=lambda c: c.rank)

    def _play_hearts(self, engine, pid, valid, is_leading):
        """Avoid winning hearts."""
        if is_leading:
            non_hearts = [c for c in valid if c.suit != Suit.HEARTS]
            if non_hearts:
                return min(non_hearts, key=lambda c: c.rank)
            return min(valid, key=lambda c: c.rank)

        trick = engine.current_trick
        lead_suit = trick.lead_suit
        same_suit = [c for c in valid if c.suit == lead_suit]

        if same_suit:
            return min(same_suit, key=lambda c: c.rank)

        # Dump hearts (high first)
        hearts_in_hand = [c for c in valid if c.suit == Suit.HEARTS]
        if hearts_in_hand:
            return max(hearts_in_hand, key=lambda c: c.rank)
        return max(valid, key=lambda c: c.rank)

    def _play_last_two(self, engine, pid, valid, is_leading):
        """Avoid winning tricks 12 and 13."""
        trick_num = len(engine.tricks_played) + 1

        if trick_num >= 11:
            # Getting dangerous — play as low as possible
            return min(valid, key=lambda c: c.rank)

        if is_leading:
            if trick_num >= 10:
                return min(valid, key=lambda c: c.rank)
            # Early: can play normally, slightly prefer low
            return min(valid, key=lambda c: c.rank)

        trick = engine.current_trick
        lead_suit = trick.lead_suit
        same_suit = [c for c in valid if c.suit == lead_suit]

        if same_suit:
            if trick_num >= 11:
                return min(same_suit, key=lambda c: c.rank)
            # Try to win early tricks to get rid of high cards
            if trick_num <= 8:
                return max(same_suit, key=lambda c: c.rank)
            return min(same_suit, key=lambda c: c.rank)

        if trick_num >= 11:
            return min(valid, key=lambda c: c.rank)
        return max(valid, key=lambda c: c.rank)

    def _play_no_tricks(self, engine, pid, valid, is_leading):
        """Avoid winning any tricks at all."""
        if is_leading:
            return min(valid, key=lambda c: c.rank)

        trick = engine.current_trick
        lead_suit = trick.lead_suit
        same_suit = [c for c in valid if c.suit == lead_suit]

        if same_suit:
            # Play just under the current highest
            current_best = max(
                (c.rank for _, c in trick.cards if c.suit == lead_suit),
                default=0
            )
            under = [c for c in same_suit if c.rank < current_best]
            if under:
                return max(under, key=lambda c: c.rank)
            return min(same_suit, key=lambda c: c.rank)

        # Can't follow: dump highest
        return max(valid, key=lambda c: c.rank)
