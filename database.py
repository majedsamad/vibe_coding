from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    Float,
    Date,
    ForeignKey,
    DateTime,
)
from sqlalchemy.orm import sessionmaker, relationship, declarative_base
from sqlalchemy.sql import func  # For default timestamp

# --- Database Setup ---
DATABASE_URL = "sqlite:///budget.db"  # Creates budget.db in the same directory

# create_engine is the starting point for any SQLAlchemy application.
# connect_args is needed for SQLite to enforce foreign key constraints.
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},  # Needed for SQLite threading
)

# SessionLocal instances will be the actual database session handles.
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for our declarative models.
Base = declarative_base()

# --- Data Models (Tables) ---


class Account(Base):
    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    # type = Column(String, nullable=True) # e.g., checking, savings, credit
    # balance = Column(Float, default=0.0) # Storing balance directly can be tricky due to transactions
    # It's often better to calculate balance from transactions or store snapshots

    # Relationship: An account can have many transactions
    transactions = relationship("Transaction", back_populates="account")
    # Relationship: An account can have many snapshot entries
    snapshots = relationship("SnapshotEntry", back_populates="account", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Account(id={self.id}, name='{self.name}')>"


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    date = Column(Date, nullable=False, index=True)
    description = Column(String, nullable=False)
    amount = Column(
        Float, nullable=False
    )  # Use negative for expenses, positive for income
    category_id = Column(
        Integer, ForeignKey("categories.id"), nullable=True, index=True
    )  # Link to Category
    account_id = Column(
        Integer, ForeignKey("accounts.id"), nullable=False, index=True
    )  # Link to Account
    notes = Column(String, nullable=True)

    # Relationships
    category = relationship("Category", back_populates="transactions")
    account = relationship("Account", back_populates="transactions")

    def __repr__(self):
        return f"<Transaction(id={self.id}, date={self.date}, desc='{self.description[:20]}', amount={self.amount})>"


class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    # budgeted_amount = Column(Float, default=0.0) # Optional: For budget planning

    # Relationship: A category can have many transactions
    transactions = relationship("Transaction", back_populates="category")

    def __repr__(self):
        return f"<Category(id={self.id}, name='{self.name}')>"


class Snapshot(Base):
    __tablename__ = "snapshots"
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    notes = Column(String, nullable=True)

    # Relationship: A snapshot consists of multiple entries (one per account)
    entries = relationship(
        "SnapshotEntry", back_populates="snapshot", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Snapshot(id={self.id}, timestamp='{self.timestamp}')>"


class SnapshotEntry(Base):
    __tablename__ = "snapshot_entries"
    id = Column(Integer, primary_key=True, index=True)
    snapshot_id = Column(
        Integer, ForeignKey("snapshots.id"), nullable=False, index=True
    )
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False, index=True)
    balance = Column(Float, nullable=False)

    # Relationships
    snapshot = relationship("Snapshot", back_populates="entries")
    account = relationship("Account", back_populates="snapshots")

    def __repr__(self):
        return f"<SnapshotEntry(id={self.id}, snapshot_id={self.snapshot_id}, account_id={self.account_id}, balance={self.balance})>"


# --- Utility Function ---
def init_db():
    """Creates database tables if they don't exist and adds default data conditionally."""
    print("Initializing database...")
    try:
        # Ensure all tables defined in Base are created if they don't exist
        Base.metadata.create_all(bind=engine)
        print("Database tables checked/created.")

        # Use a session to check and potentially add default data
        with SessionLocal() as db:
            # --- 1. Ensure default category exists (usually always needed) ---
            uncategorized_added = False
            uncategorized_exists = (
                db.query(Category).filter(Category.name == "Uncategorized").count() > 0
            )
            if not uncategorized_exists:
                print("Adding default 'Uncategorized' category...")
                default_cat = Category(name="Uncategorized")
                db.add(default_cat)
                uncategorized_added = True # Mark that we added it

            # --- 2. Check if ANY accounts exist ---
            total_account_count = db.query(Account).count()
            defaults_added = False # Flag to track if we add defaults in this run

            # --- 3. Add default accounts ONLY if NO accounts exist ---
            if total_account_count == 0:
                print("No accounts found. Adding default accounts...")
                default_account_names = ["Cash", "Checking", "Savings", "Brokerage"]
                for acc_name in default_account_names:
                    # Since we know the table is empty, no need for individual checks
                    print(f"Adding default account: '{acc_name}'...")
                    default_acc = Account(name=acc_name)
                    db.add(default_acc)
                defaults_added = True # Mark that we added the block of defaults
            else:
                # If accounts already exist, skip adding defaults
                print(f"Found {total_account_count} existing account(s). Skipping default account creation.")

            # --- 4. Commit if any changes were made ---
            if uncategorized_added or defaults_added:
                db.commit()
                print("Default data checked/added.")
            else:
                # Provide feedback if nothing was added
                if uncategorized_exists and total_account_count > 0:
                    print("Default category and existing accounts found. No default data added.")
                elif uncategorized_exists:
                     print("Default category found. No default accounts added (table was empty).") # Should not happen with current logic but safe
                # Add other conditions if needed

    except Exception as e:
        print(f"Error during database initialization: {e}")
        # Rollback might be needed if error occurred mid-session, but context manager handles it


if __name__ == "__main__":
    # This allows running 'python database.py' to create the DB schema
    print("Running database setup directly...")
    init_db()
    print("Setup complete.")
