"""
Rıfkı (King) - Card Game Engine
================================
A Turkish trick-taking compendium card game for 4 players.
20 rounds total, each player declares 5 contracts (2 Trump + 3 Negative).

House Rules:
- First 4 rounds: no Trump allowed (must pick negative)
- Rıfkı misdeal: if any player has only K♥, only A♥, or only K♥+A♥ (no other hearts)
- Girls misdeal: if each player gets exactly 1 Queen, round doesn't count
"""

import random
from enum import Enum
from typing import List, Optional, Dict, Tuple


class Suit(Enum):
    HEARTS = 'hearts'
    DIAMONDS = 'diamonds'
    CLUBS = 'clubs'
    SPADES = 'spades'


class ContractType(Enum):
    TRUMP = 'trump'
    RIFKI = 'rifki'
    GIRLS = 'girls'
    BOYS = 'boys'
    HEARTS = 'hearts'
    LAST_TWO = 'last_two'
    NO_TRICKS = 'no_tricks'


SUIT_SYMBOLS = {
    Suit.HEARTS: '♥', Suit.DIAMONDS: '♦',
    Suit.CLUBS: '♣', Suit.SPADES: '♠'
}

RANK_NAMES = {
    2: '2', 3: '3', 4: '4', 5: '5', 6: '6', 7: '7', 8: '8',
    9: '9', 10: '10', 11: 'J', 12: 'Q', 13: 'K', 14: 'A'
}

CONTRACT_DISPLAY = {
    ContractType.TRUMP: 'Trump (Koz)',
    ContractType.RIFKI: 'Rıfkı (K♥)',
    ContractType.GIRLS: 'Girls (Kız)',
    ContractType.BOYS: 'Boys (Erkek)',
    ContractType.HEARTS: 'Hearts (Kupa)',
    ContractType.LAST_TWO: 'Last Two (Son İki)',
    ContractType.NO_TRICKS: 'No Tricks (El Almaz)',
}


class Card:
    __slots__ = ('suit', 'rank')

    def __init__(self, suit: Suit, rank: int):
        self.suit = suit
        self.rank = rank

    def __str__(self):
        return f"{RANK_NAMES[self.rank]}{SUIT_SYMBOLS[self.suit]}"

    def __eq__(self, other):
        return isinstance(other, Card) and self.suit == other.suit and self.rank == other.rank

    def __hash__(self):
        return hash((self.suit, self.rank))

    def __repr__(self):
        return str(self)

    def to_dict(self):
        return {
            'suit': self.suit.value,
            'rank': self.rank,
            'display': str(self),
            'rank_name': RANK_NAMES[self.rank]
        }


class Trick:
    def __init__(self):
        self.cards: List[Tuple[int, Card]] = []
        self.lead_suit: Optional[Suit] = None

    def add_card(self, player_id: int, card: Card):
        if not self.cards:
            self.lead_suit = card.suit
        self.cards.append((player_id, card))

    def get_winner(self, trump_suit: Optional[Suit] = None) -> int:
        best_pid, best_card = self.cards[0]
        for pid, card in self.cards[1:]:
            beats = False
            if trump_suit:
                if card.suit == trump_suit and best_card.suit != trump_suit:
                    beats = True
                elif card.suit == trump_suit and best_card.suit == trump_suit:
                    beats = card.rank > best_card.rank
                elif card.suit == self.lead_suit and best_card.suit == self.lead_suit:
                    beats = card.rank > best_card.rank
                elif card.suit == self.lead_suit and best_card.suit != self.lead_suit and best_card.suit != trump_suit:
                    beats = True
            else:
                if card.suit == self.lead_suit and best_card.suit == self.lead_suit:
                    beats = card.rank > best_card.rank
                elif card.suit == self.lead_suit and best_card.suit != self.lead_suit:
                    beats = True
            if beats:
                best_pid, best_card = pid, card
        return best_pid

    def to_dict(self):
        return {
            'cards': [{'player_id': pid, 'card': c.to_dict()} for pid, c in self.cards],
            'lead_suit': self.lead_suit.value if self.lead_suit else None
        }


class Player:
    def __init__(self, pid: int, name: str, is_human: bool):
        self.id = pid
        self.name = name
        self.is_human = is_human
        self.hand: List[Card] = []
        self.total_score: int = 0
        self.contracts_declared: List[ContractType] = []
        self.trump_count: int = 0
        self.round_scores: List[dict] = []

    def get_available_contracts(self, contracts_used: Dict[ContractType, int], round_number: int) -> List[ContractType]:
        available = []
        can_play_trump = round_number > 4  # House rule: first 4 rounds no trump
        negative_count = len(self.contracts_declared) - self.trump_count
        remaining = 5 - len(self.contracts_declared)
        remaining_trump_needed = 2 - self.trump_count

        # Must play trump if remaining rounds == remaining trump needed
        if remaining == remaining_trump_needed and can_play_trump:
            return [ContractType.TRUMP]

        # Add trump if allowed
        if self.trump_count < 2 and can_play_trump and negative_count >= 3:
            # Already have 3 negatives, must play trump
            return [ContractType.TRUMP]

        if self.trump_count < 2 and can_play_trump:
            available.append(ContractType.TRUMP)

        # Add available negative contracts
        if negative_count < 3:
            for ct in [ContractType.RIFKI, ContractType.GIRLS, ContractType.BOYS,
                       ContractType.HEARTS, ContractType.LAST_TWO, ContractType.NO_TRICKS]:
                if contracts_used.get(ct, 0) < 2:
                    available.append(ct)

        return available

    def sort_hand(self):
        suit_order = {Suit.SPADES: 0, Suit.HEARTS: 1, Suit.DIAMONDS: 2, Suit.CLUBS: 3}
        self.hand.sort(key=lambda c: (suit_order[c.suit], c.rank))

    def to_dict(self, hide_hand=False):
        return {
            'id': self.id,
            'name': self.name,
            'is_human': self.is_human,
            'hand': [] if hide_hand else [c.to_dict() for c in self.hand],
            'hand_count': len(self.hand),
            'total_score': self.total_score,
            'contracts_declared': [c.value for c in self.contracts_declared],
            'trump_count': self.trump_count,
            'round_scores': self.round_scores
        }


class GameEngine:
    def __init__(self, player_names: List[str], human_indices: List[int]):
        self.players = [
            Player(i, name, i in human_indices)
            for i, name in enumerate(player_names)
        ]
        self.round_number = 0
        self.declarer_index = -1
        self.current_contract: Optional[ContractType] = None
        self.trump_suit: Optional[Suit] = None
        self.tricks_played: List[Trick] = []
        self.current_trick: Optional[Trick] = None
        self.current_player_index: int = -1
        self.hearts_broken: bool = False
        self.contracts_used: Dict[ContractType, int] = {}
        self.penalty_cards_taken: Dict[int, List[Card]] = {i: [] for i in range(4)}
        self.tricks_won: Dict[int, int] = {i: 0 for i in range(4)}
        self.game_over: bool = False
        self.state: str = 'waiting'
        self.scoreboard: List[Dict] = []
        self.last_trick_result: Optional[dict] = None

    def create_deck(self) -> List[Card]:
        return [Card(suit, rank) for suit in Suit for rank in range(2, 15)]

    def deal(self):
        deck = self.create_deck()
        random.shuffle(deck)
        for p in self.players:
            p.hand = []
        for i, card in enumerate(deck):
            self.players[i % 4].hand.append(card)
        for p in self.players:
            p.sort_hand()

    def find_two_of_diamonds(self) -> int:
        for p in self.players:
            for c in p.hand:
                if c.suit == Suit.DIAMONDS and c.rank == 2:
                    return p.id
        return 0

    def start_new_round(self) -> dict:
        self.round_number += 1
        self.current_contract = None
        self.trump_suit = None
        self.tricks_played = []
        self.current_trick = None
        self.hearts_broken = False
        self.penalty_cards_taken = {i: [] for i in range(4)}
        self.tricks_won = {i: 0 for i in range(4)}
        self.last_trick_result = None

        self.deal()

        if self.round_number == 1:
            self.declarer_index = self.find_two_of_diamonds()
        else:
            self.declarer_index = (self.declarer_index - 1) % 4  # counter-clockwise

        self.state = 'contract_selection'
        self.current_player_index = self.declarer_index

        return {
            'round': self.round_number,
            'declarer': self.declarer_index,
            'declarer_name': self.players[self.declarer_index].name
        }

    def check_rifki_misdeal(self) -> bool:
        """House rule: misdeal if any player has only K♥, only A♥, or only K♥+A♥."""
        for p in self.players:
            hearts = [c for c in p.hand if c.suit == Suit.HEARTS]
            if not hearts:
                continue
            ranks = {c.rank for c in hearts}
            if ranks in [{13}, {14}, {13, 14}]:
                return True
        return False

    def get_available_contracts(self) -> List[str]:
        player = self.players[self.declarer_index]
        contracts = player.get_available_contracts(self.contracts_used, self.round_number)
        return [c.value for c in contracts]

    def set_contract(self, contract_value: str, trump_suit_value: Optional[str] = None) -> dict:
        try:
            contract_type = ContractType(contract_value)
        except ValueError:
            return {'success': False, 'error': f'Invalid contract: {contract_value}'}

        player = self.players[self.declarer_index]
        available = player.get_available_contracts(self.contracts_used, self.round_number)

        if contract_type not in available:
            return {'success': False, 'error': f'{contract_value} not available'}

        if contract_type == ContractType.TRUMP:
            if trump_suit_value is None:
                self.current_contract = ContractType.TRUMP
                self.state = 'trump_selection'
                return {'success': True, 'need_trump_suit': True}
            try:
                self.trump_suit = Suit(trump_suit_value)
            except ValueError:
                return {'success': False, 'error': f'Invalid suit: {trump_suit_value}'}
            player.trump_count += 1

        self.current_contract = contract_type
        player.contracts_declared.append(contract_type)
        self.contracts_used[contract_type] = self.contracts_used.get(contract_type, 0) + 1

        # Check Rıfkı misdeal
        if contract_type == ContractType.RIFKI and self.check_rifki_misdeal():
            player.contracts_declared.pop()
            self.contracts_used[contract_type] -= 1
            self.current_contract = None
            return {
                'success': False, 'misdeal': True,
                'reason': 'Rıfkı misdeal: A player has only K♥, only A♥, or only K♥+A♥'
            }

        self.state = 'playing'
        self.current_player_index = self.declarer_index
        self.current_trick = Trick()
        return {'success': True, 'contract': contract_type.value}

    def set_trump_suit(self, suit_value: str) -> dict:
        try:
            self.trump_suit = Suit(suit_value)
        except ValueError:
            return {'success': False, 'error': f'Invalid suit: {suit_value}'}

        player = self.players[self.declarer_index]
        player.trump_count += 1
        player.contracts_declared.append(ContractType.TRUMP)
        self.contracts_used[ContractType.TRUMP] = self.contracts_used.get(ContractType.TRUMP, 0) + 1

        self.state = 'playing'
        self.current_player_index = self.declarer_index
        self.current_trick = Trick()
        return {'success': True, 'trump_suit': self.trump_suit.value}

    def is_penalty_card(self, card: Card) -> bool:
        if self.current_contract == ContractType.RIFKI:
            return card.suit == Suit.HEARTS and card.rank == 13
        elif self.current_contract == ContractType.GIRLS:
            return card.rank == 12
        elif self.current_contract == ContractType.BOYS:
            return card.rank in (11, 13)
        elif self.current_contract == ContractType.HEARTS:
            return card.suit == Suit.HEARTS
        return False

    def get_valid_cards(self, player_id: int) -> List[Card]:
        player = self.players[player_id]
        hand = player.hand
        if not hand:
            return []

        # Leading
        if not self.current_trick or not self.current_trick.cards:
            if self.current_contract in (ContractType.RIFKI, ContractType.HEARTS):
                if not self.hearts_broken:
                    non_hearts = [c for c in hand if c.suit != Suit.HEARTS]
                    if non_hearts:
                        return non_hearts
            return list(hand)

        # Following suit
        lead_suit = self.current_trick.lead_suit
        same_suit = [c for c in hand if c.suit == lead_suit]

        if same_suit:
            return same_suit

        # Can't follow suit
        if self.current_contract == ContractType.TRUMP:
            trumps = [c for c in hand if c.suit == self.trump_suit]
            if trumps:
                return trumps
            return list(hand)
        elif self.current_contract == ContractType.RIFKI:
            # Rıfkı rule: if you can't follow suit, you MUST play hearts
            hearts = [c for c in hand if c.suit == Suit.HEARTS]
            if hearts:
                return hearts
            return list(hand)
        else:
            # Other negative contracts: prefer penalty cards, otherwise any
            penalty = [c for c in hand if self.is_penalty_card(c)]
            if penalty:
                return penalty
            return list(hand)

    def play_card(self, player_id: int, card_dict: dict) -> dict:
        if player_id != self.current_player_index:
            return {'success': False, 'error': 'Not your turn'}

        card = Card(Suit(card_dict['suit']), card_dict['rank'])
        player = self.players[player_id]

        if card not in player.hand:
            return {'success': False, 'error': 'Card not in hand'}

        valid = self.get_valid_cards(player_id)
        if card not in valid:
            return {'success': False, 'error': 'Invalid card for current rules'}

        player.hand.remove(card)
        self.current_trick.add_card(player_id, card)

        # Hearts broken check
        if card.suit == Suit.HEARTS and not self.hearts_broken:
            if len(self.current_trick.cards) > 1 or self.current_trick.lead_suit != Suit.HEARTS:
                self.hearts_broken = True

        # Trick complete?
        if len(self.current_trick.cards) == 4:
            return self._resolve_trick()

        self.current_player_index = (self.current_player_index - 1) % 4
        return {
            'success': True,
            'trick_complete': False,
            'next_player': self.current_player_index,
            'card': card.to_dict()
        }

    def _resolve_trick(self) -> dict:
        winner = self.current_trick.get_winner(self.trump_suit)
        self.tricks_won[winner] = self.tricks_won.get(winner, 0) + 1

        for _, card in self.current_trick.cards:
            if self.is_penalty_card(card):
                self.penalty_cards_taken[winner].append(card)

        trick_data = self.current_trick.to_dict()
        trick_data['winner'] = winner
        trick_data['trick_number'] = len(self.tricks_played) + 1

        self.tricks_played.append(self.current_trick)

        # Check round over
        round_over = len(self.tricks_played) == 13
        if not round_over and self.current_contract in (
            ContractType.RIFKI, ContractType.GIRLS, ContractType.BOYS, ContractType.HEARTS
        ):
            total = sum(len(v) for v in self.penalty_cards_taken.values())
            maxp = {ContractType.RIFKI: 1, ContractType.GIRLS: 4,
                    ContractType.BOYS: 8, ContractType.HEARTS: 13}
            if total >= maxp[self.current_contract]:
                round_over = True

        if round_over:
            return self._end_round(trick_data)

        self.current_trick = Trick()
        self.current_player_index = winner
        self.last_trick_result = trick_data

        return {
            'success': True, 'trick_complete': True,
            'trick': trick_data, 'round_over': False,
            'next_player': winner
        }

    def _end_round(self, last_trick) -> dict:
        scores = {i: 0 for i in range(4)}

        if self.current_contract == ContractType.TRUMP:
            for trick in self.tricks_played:
                w = trick.get_winner(self.trump_suit)
                scores[w] += 50

        elif self.current_contract == ContractType.RIFKI:
            for pid, cards in self.penalty_cards_taken.items():
                scores[pid] -= 320 * len(cards)

        elif self.current_contract == ContractType.GIRLS:
            # House rule: each player exactly 1 queen → misdeal
            per_player = {i: len(cards) for i, cards in self.penalty_cards_taken.items()}
            if all(v == 1 for v in per_player.values()):
                p = self.players[self.declarer_index]
                p.contracts_declared.pop()
                self.contracts_used[ContractType.GIRLS] -= 1
                self.current_contract = None
                self.state = 'contract_selection'
                self.deal()
                return {
                    'success': True, 'trick_complete': True,
                    'trick': last_trick, 'round_over': True,
                    'girls_misdeal': True,
                    'reason': 'Each player got exactly 1 Queen — round void, reshuffling!',
                    'round_number': self.round_number
                }
            for pid, cards in self.penalty_cards_taken.items():
                scores[pid] -= 100 * len(cards)

        elif self.current_contract == ContractType.BOYS:
            for pid, cards in self.penalty_cards_taken.items():
                scores[pid] -= 60 * len(cards)

        elif self.current_contract == ContractType.HEARTS:
            for pid, cards in self.penalty_cards_taken.items():
                scores[pid] -= 30 * len(cards)

        elif self.current_contract == ContractType.LAST_TWO:
            for trick in self.tricks_played[-2:]:
                w = trick.get_winner(self.trump_suit)
                scores[w] -= 180

        elif self.current_contract == ContractType.NO_TRICKS:
            for trick in self.tricks_played:
                w = trick.get_winner(self.trump_suit)
                scores[w] -= 50

        # Update totals
        for pid, s in scores.items():
            self.players[pid].total_score += s
            self.players[pid].round_scores.append({
                'round': self.round_number,
                'contract': self.current_contract.value,
                'declarer': self.declarer_index,
                'score': s
            })

        self.scoreboard.append({
            'round': self.round_number,
            'declarer': self.players[self.declarer_index].name,
            'declarer_id': self.declarer_index,
            'contract': self.current_contract.value,
            'contract_display': CONTRACT_DISPLAY.get(self.current_contract, ''),
            'trump_suit': self.trump_suit.value if self.trump_suit else None,
            'scores': scores,
            'totals': {i: self.players[i].total_score for i in range(4)}
        })

        if self.round_number >= 20:
            self.state = 'game_over'
            self.game_over = True
        else:
            self.state = 'round_end'

        return {
            'success': True, 'trick_complete': True,
            'trick': last_trick, 'round_over': True,
            'round_scores': scores,
            'total_scores': {i: self.players[i].total_score for i in range(4)},
            'game_over': self.game_over
        }

    def get_state(self, for_player: Optional[int] = None) -> dict:
        return {
            'round_number': self.round_number,
            'state': self.state,
            'declarer': self.declarer_index,
            'declarer_name': self.players[self.declarer_index].name if self.declarer_index >= 0 else '',
            'current_contract': self.current_contract.value if self.current_contract else None,
            'contract_display': CONTRACT_DISPLAY.get(self.current_contract, '') if self.current_contract else '',
            'trump_suit': self.trump_suit.value if self.trump_suit else None,
            'current_player': self.current_player_index,
            'tricks_played_count': len(self.tricks_played),
            'hearts_broken': self.hearts_broken,
            'current_trick': self.current_trick.to_dict() if self.current_trick else None,
            'players': [
                p.to_dict(hide_hand=(for_player is not None and p.id != for_player))
                for p in self.players
            ],
            'scoreboard': self.scoreboard,
            'contracts_used': {k.value: v for k, v in self.contracts_used.items()},
            'game_over': self.game_over,
            'tricks_won': self.tricks_won,
            'penalty_cards': {
                pid: [c.to_dict() for c in cards]
                for pid, cards in self.penalty_cards_taken.items()
            }
        }
