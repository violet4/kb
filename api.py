# Auto-generated API surface — REFERENCE ONLY, not an importable module.
# Import from models.py instead: `from models import Note, sess, ...`
# Run `uv run scripts/dev/gen-api` to regenerate after changing models.py.

# Session
sess  # scoped_session — pre-loaded in kb.py and scripts

# Enums
Collection: ENGINEERING | PERSONAL | GORGON | WORK | ALL
GoalStatus: ACTIVE | COMPLETED | ABANDONED
PersonTier: CLOSE | ACQUAINTANCE | PUBLIC_FIGURE
TodoStatus: PENDING | IN_PROGRESS | DONE | DROPPED
WishlistEffort: GRAB | RESEARCH | PROJECT
WishlistStatus: ACTIVE | ACQUIRED | DROPPED

ChangeLog
  .id: Integer
  .entity_table: String
  .entity_id: Integer
  .field: String
  .old_value: Text?
  .new_value: Text?
  .changed_at: DateTime
  .created_at: DateTime
  .updated_at: DateTime


Context
  .id: Integer
  .name: String
  .description: Text?
  .created_at: DateTime
  .updated_at: DateTime

  @classmethod .get_or_create(name: str, description: Optional[str]=None) -> Context

CurrentContext
  .id: Integer
  .context_id: Integer?
  .created_at: DateTime
  .updated_at: DateTime
  .context: Context  # relationship

  @classmethod .get() -> Optional[Context]
  @classmethod .set(context: Optional[Context]) -> None

Daily
  .id: Integer
  .description: String
  .context_id: Integer?
  .location: String?
  .reward: Text?
  .is_active: Boolean
  .notes: Text?
  .created_at: DateTime
  .updated_at: DateTime
  .context: Context  # relationship

  @classmethod .active(context: Optional[Context]=None) -> list[Daily]
  @classmethod .create(description: str, context: Optional[Context]=None, location: Optional[str]=None, reward: Optional[str]=None, notes: Optional[str]=None) -> Daily

Goal
  .id: Integer
  .title: String
  .description: Text?
  .status: GoalStatus
  .context_id: Integer?
  .notes: Text?
  .created_at: DateTime
  .updated_at: DateTime
  .context: Context  # relationship
  .todos: Todo  # relationship

  @classmethod .active(context: Optional[Context]=None) -> list[Goal]
  @classmethod .create(title: str, description: Optional[str]=None, context: Optional[Context]=None, notes: Optional[str]=None) -> Goal

Item
  .id: Integer
  .game: String
  .name: String
  .context_id: Integer?
  .notes: Text?
  .created_at: DateTime
  .updated_at: DateTime
  .context: Context  # relationship

  @classmethod .by_game(game: str) -> list[Item]

Note
  .id: Integer
  .title: String
  .body: Text
  .collection: Collection
  .tags: String?
  .embedding_model: String?
  .embedding: Text?
  .created_at: DateTime
  .updated_at: DateTime

  @classmethod .create(title: str, body: str, collection: Collection, tags: Optional[str]=None) -> Note
  @classmethod .find(title: str) -> Optional[Note]
  @classmethod .get(id: int) -> Optional[Note]
  .reembed() -> None
  @classmethod .search(query: str, collection: Collection) -> list[tuple[Note, float]]
  .update(title: Optional[str]=None, body: Optional[str]=None, tags: Optional[str]=None) -> None

Person
  .id: Integer
  .name: String
  .tier: PersonTier
  .closeness: Integer
  .last_contacted: DateTime?
  .reach_out_every_days: Integer?
  .notes: Text?
  .created_at: DateTime
  .updated_at: DateTime

  @classmethod .get(name: str) -> Optional[Person]
  @classmethod .get_or_create(name: str, tier: PersonTier=<PersonTier.ACQUAINTANCE: 'acquaintance'>) -> Person
  @classmethod .in_my_life() -> list[Person]  # People who are part of my immediate surrounding life (excludes public figures).
  @classmethod .overdue_for_contact() -> list[Person]  # People I should have reached out to by now, ordered by most overdue.

PgItem
  .id: Integer
  .game: String
  .name: String
  .context_id: Integer?
  .notes: Text?
  .created_at: DateTime
  .updated_at: DateTime
  .id: Integer
  .kind: String?
  .sources: Text?
  .max_stack_size: Integer?
  .context: Context  # relationship

  @classmethod .by_game(game: str) -> list[Item]

Reference
  .id: Integer
  .title: String
  .url: String?
  .tags: String?
  .context_id: Integer?
  .notes: Text?
  .created_at: DateTime
  .updated_at: DateTime
  .context: Context  # relationship

  @classmethod .create(title: str, url: Optional[str]=None, tags: Optional[str]=None, context: Optional[Context]=None, notes: Optional[str]=None) -> Reference
  @classmethod .search(query: str) -> list[Reference]

Todo
  .id: Integer
  .title: String
  .status: TodoStatus
  .goal_id: Integer?
  .context_id: Integer?
  .blocked_by_id: Integer?
  .notes: Text?
  .created_at: DateTime
  .updated_at: DateTime
  .goal: Goal  # relationship
  .context: Context  # relationship
  .blocked_by: Todo  # relationship

  @classmethod .create(title: str, goal: Optional[Goal]=None, context: Optional[Context]=None, notes: Optional[str]=None, blocked_by: Optional[Todo]=None) -> Todo
  @classmethod .pending(context: Optional[Context]=None) -> list[Todo]

Wishlist
  .id: Integer
  .title: String
  .description: Text?
  .price_min: Numeric?
  .price_max: Numeric?
  .importance: Integer
  .urgency: Integer
  .effort: WishlistEffort
  .clarity: Integer
  .priority: Integer?
  .status: WishlistStatus
  .context_id: Integer?
  .notes: Text?
  .created_at: DateTime
  .updated_at: DateTime
  .context: Context  # relationship

  @classmethod .active(effort: Optional[WishlistEffort]=None) -> list[Wishlist]
  @classmethod .top(n: int=10) -> list[Wishlist]  # Active items: explicit priority first (nulls last), then score as tiebreaker.

WorkingMemory
  .id: Integer
  .topic: String
  .domain: String?
  .body: Text
  .context_id: Integer?
  .created_at: DateTime
  .updated_at: DateTime
  .context: Context  # relationship

  @classmethod .get(topic: str) -> Optional[WorkingMemory]
  @classmethod .get_or_create(topic: str, domain: Optional[str]=None, body: str='') -> WorkingMemory
  @classmethod .search(query: str) -> list[WorkingMemory]
