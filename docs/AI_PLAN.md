# Rıfkı AI — Professional Play Implementation Plan

## Overview

Build a world-class AI player for the Turkish trick-taking card game **Rıfkı (King)**. The AI must master 7 contract types across 20 rounds, making optimal decisions for both contract selection and card play.

---

## Difficulty Levels

| Level | Name | Target Skill | Description |
|-------|------|-------------|-------------|
| 🟢 Easy | Casual | Casual player | Random legal plays, basic avoidance |
| 🟡 Medium | Regular | Regular player | Follows suit rules, avoids obvious penalties |
| 🔴 Hard | Experienced | Experienced player | Card counting, positional play, strategic dumps |
| 💀 Expert | Tournament | Tournament-level | Monte Carlo + perfect memory + endgame solver |

---

## Phase 1: Enhanced Heuristics (Hard Level)

**Goal**: Make the "Hard" AI play at experienced-player level.  
**Effort**: 2-3 days  
**Files**: `ai_player.py`

### 1.1 Card Memory System

Track every card played throughout the round. Track void suits per opponent (when they fail to follow suit). Count remaining cards in each suit.

```python
class CardTracker:
    """Tracks all 52 cards: in_hand, played, unknown"""
    def __init__(self):
        self.played = []           # Cards already played (by whom)
        self.void_suits = {0: set(), 1: set(), 2: set(), 3: set()}  
    
    def on_card_played(self, player_id, card, lead_suit):
        self.played.append((player_id, card))
        if card.suit != lead_suit:
            self.void_suits[player_id].add(lead_suit)
    
    def remaining_in_suit(self, suit):
        """How many cards of this suit are still unplayed?"""
        ...
```

### 1.2 Contract-Specific Strategies

#### Kız (Girls) — Avoid Queens (-100 each)
| Situation | Strategy |
|-----------|----------|
| Have Q, high cards in suit | Lead low in that suit to flush out higher cards early |
| Void in a suit with Q outstanding | Good — can sluff safely |
| Playing 4th in trick | Safe to play high if no Q in trick and Q already played |
| Holding Q alone in suit | Lead it early when opponents likely have higher cards |
| All 4 Queens accounted for | Play freely — no more penalty risk |

#### Erkek (Boys) — Avoid Jacks & Kings (-60 each)
| Situation | Strategy |
|-----------|----------|
| Have J or K | Lead low in that suit, hope someone takes the trick |
| Void in danger suit | Sluff J/K from other suits |
| Counting: 8 boys total | Track each one; play aggressively once all 8 are gone |

#### Kupa (Hearts) — Avoid Hearts (-30 each)
| Situation | Strategy |
|-----------|----------|
| Void in hearts | Play last in other suits, avoid winning tricks with hearts in play |
| Leading | Never lead hearts unless forced |
| Long heart suit | Try to void another suit early to sluff hearts |

#### Rıfkı — Avoid K♥ (-320!)
| Situation | Strategy |
|-----------|----------|
| Have K♥ | Play it when you're NOT winning the trick |
| Have A♥ | Hold it — use it to capture K♥ from opponents |
| K♥ is still out | Avoid winning heart tricks at all costs |
| K♥ has been played | No more risk — play normally |
| **RULE**: Can't follow suit? | MUST play hearts if you have them |

#### Son İki (Last Two) — Avoid Last 2 Tricks (-180 each)
| Situation | Strategy |
|-----------|----------|
| Tricks 1-10 | Play normally, try to win tricks |
| Tricks 11 | Start dumping high cards to avoid winning trick 12-13 |
| Trick 12-13 | Play lowest possible card |

#### El Almaz (No Tricks) — Avoid ALL Tricks (-50 each)
| Situation | Strategy |
|-----------|----------|
| Always | Play lowest legal card |
| Have only high cards in suit | Lead short suits to void them |
| Void in lead suit | Great — dump highest card from hand |

#### Koz (Trump) — Win Tricks (+50 each)
| Situation | Strategy |
|-----------|----------|
| 5+ trumps | Lead trumps to pull opponents' trumps |
| Short trump | Save trumps for ruffing |
| Long side suit (A-K-Q) | Cash winners after drawing trumps |

### 1.3 Positional Play

| Position | Advantage | Strategy |
|----------|-----------|----------|
| 1st (Lead) | Control | Lead weak suits in neg, strong in trump |
| 2nd | Some info | Play based on leader's card |
| 3rd | More info | Know 2 of 3 opponents' plays |
| 4th | Perfect info | See all 3 cards, play optimally |

### 1.4 Contract Selection Intelligence

Evaluate hand strength for each available contract:
- **Kız**: Score = (4 - queen_count) × 20 + low_card_ratio × 20
- **Erkek**: Score based on J/K count and ability to void suits
- **Trump**: Score = longest_suit_length × 10 + high_cards × 8
- Each contract gets a 0-100 score; pick highest

---

## Phase 2: Monte Carlo Simulation (Expert Level)

**Goal**: Near-perfect play through statistical simulation.  
**Effort**: 1-2 weeks  
**New file**: `ai_mcts.py`

### How It Works

1. AI needs to play a card
2. Generate 500 random deals of unseen cards
3. For each deal, simulate all remaining play (using heuristic AI)
4. Average the outcomes for each legal card choice
5. Pick card with best average score

### Optimizations
- **Void-aware dealing**: Don't deal suits to players known to be void
- **Early cutoff**: Stop simulating if result is already clear
- **Parallel processing**: Use multiprocessing for speed
- **Cache**: Memoize identical game states

---

## Phase 3: Reinforcement Learning (Superhuman Level)

**Goal**: AI discovers strategies beyond human intuition.  
**Effort**: 3-6 weeks  
**Stack**: PyTorch + custom training loop

### State Encoding
- My hand: 52-bit vector
- Played cards: 52-bit vector
- Current trick: 4 × 52-bit
- Void info: 4 × 4
- Contract type: 7-dim one-hot
- Trick count + position + scores
- **Total: ~280 features**

### Training Timeline

| Phase | Games | Time | Expected Level |
|-------|-------|------|---------------|
| Initial | 100K | ~2 hours | Worse than Easy |
| Basic | 1M | ~8 hours | Medium level |
| Competent | 10M | ~3 days | Hard level |
| Expert | 100M | ~2 weeks | Expert level |
| Mastery | 500M+ | ~1 month | Superhuman? |

---

## Difficulty Level Feature Matrix

| Feature | 🟢 Easy | 🟡 Medium | 🔴 Hard | 💀 Expert |
|---------|---------|-----------|---------|-----------|
| Follow suit rules | ✓ | ✓ | ✓ | ✓ |
| Avoid obvious penalties | — | ✓ | ✓ | ✓ |
| Card counting | — | — | ✓ | ✓ |
| Void tracking | — | — | ✓ | ✓ |
| Positional play | — | — | ✓ | ✓ |
| Endgame calculation | — | — | Partial | ✓ |
| Monte Carlo lookahead | — | — | — | ✓ |
| Contract evaluation | Random | Basic | Smart | Optimal |
| Think time per move | 0ms | 0ms | 0ms | 200-500ms |

---

## Implementation Order

1. **Week 1**: Implement `CardTracker` + void detection (Phase 1.1)
2. **Week 1**: Add contract-specific play rules (Phase 1.2)
3. **Week 1**: Wire up difficulty levels (Easy/Medium/Hard selector in UI)
4. **Week 2**: Build Monte Carlo player (Phase 2)
5. **Week 2**: Add Expert difficulty option
6. **Week 3+**: Optional RL training (Phase 3)

---

## Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `ai_player.py` | Modify | Add CardTracker, enhance strategies, difficulty param |
| `ai_mcts.py` | Create | Monte Carlo simulation player |
| `ai_rl.py` | Create | (Optional) RL training + inference |
| `server.py` | Modify | Pass difficulty level from UI to AI |
| `templates/index.html` | Modify | Add AI difficulty selector in lobby |
| `templates/game.html` | Modify | Show AI difficulty indicator |

---

## Success Metrics

| Metric | Target |
|--------|--------|
| Easy vs Human beginner | Human wins 80%+ |
| Medium vs Casual player | 50/50 |
| Hard vs Experienced player | AI wins 45%+ |
| Expert vs Expert human | AI wins 50%+ |
