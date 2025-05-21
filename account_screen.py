from kivy.uix.screenmanager import Screen
from kivy.properties import ObjectProperty
from kivy.uix.label import Label
from kivy.factory import Factory
from kivy.metrics import dp
from kivy.clock import Clock
from sqlalchemy.orm import joinedload # For efficient querying

from database import SessionLocal, Account, Snapshot, SnapshotEntry


class AccountsScreen(Screen):
    snapshot_status_label = ObjectProperty(None)
    account_list_layout = ObjectProperty(None)  # Reference to the GridLayout

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Dictionary to store references: {account_id: balance_input_widget}
        self.account_inputs = {}
        # --- NEW: Dictionary to store references to last balance labels ---
        # {account_id: last_balance_label_widget}
        self.last_balance_labels = {}

    def on_enter(self, *args):
        """Called when the screen is displayed. Schedule the UI setup."""
        # Schedule the actual setup for the next frame to ensure widgets are ready
        Clock.schedule_once(self._setup_ui, 0)  # 0 schedules for the very next frame

    def _setup_ui(self, dt):  # dt is the time delta passed by Clock
        """This method runs after on_enter, when widgets should be bound."""
        print("Entering Accounts Screen (_setup_ui). Loading accounts...")

        # Defensive check (optional but good practice)
        if not self.snapshot_status_label or not self.account_list_layout:
            print("Error: UI elements not ready even after scheduling. Aborting setup.")
            # You could try rescheduling again: Clock.schedule_once(self._setup_ui, 0.1)
            return

        self.snapshot_status_label.text = (
            "Enter current balances above."  # Reset status
        )
        self.load_accounts_ui()  # Now load the accounts

    def load_accounts_ui(self):
        """Queries DB for accounts, finds the latest snapshot balance for each,
           and populates the GridLayout, storing label references."""
        if not self.account_list_layout:
            print("Error: Account list layout not ready.")
            # ... (error handling) ...
            return

        # --- Clear label references BEFORE clearing widgets ---
        self.account_inputs.clear()
        self.last_balance_labels.clear() # Clear the label refs too
        self.account_list_layout.clear_widgets()


        latest_balances = {}

        try:
            with SessionLocal() as db:
                # ... (Querying accounts and latest balances remains the same) ...
                accounts = db.query(Account).order_by(Account.name).all()
                if not accounts:
                    self.snapshot_status_label.text = "No accounts found. Add accounts in 'Manage Accounts'."
                    return

                account_ids = [acc.id for acc in accounts]
                # ... (Query and process all_entries to populate latest_balances) ...
                all_entries = (
                     db.query(SnapshotEntry)
                     .options(joinedload(SnapshotEntry.snapshot))
                     .filter(SnapshotEntry.account_id.in_(account_ids))
                     .join(SnapshotEntry.snapshot)
                     .order_by(SnapshotEntry.account_id, Snapshot.timestamp.desc())
                     .all()
                 )
                processed_accounts = set()
                for entry in all_entries:
                    if entry.account_id not in processed_accounts:
                        latest_balances[entry.account_id] = entry.balance
                        processed_accounts.add(entry.account_id)


                # 3. Populate the UI
                for account in accounts:
                    last_balance = latest_balances.get(account.id)
                    last_balance_str = f"{last_balance:.2f}" if last_balance is not None else "N/A"

                    # --- Column 1: Account Name ---
                    name_label = Label(
                        text=account.name, size_hint_y=None, height=dp(40),
                        halign="left", valign="middle", size_hint_x=0.40
                    )
                    name_label.bind(width=lambda instance, width: setattr(instance, 'text_size', (width, None)))
                    self.account_list_layout.add_widget(name_label)

                    # --- Column 2: Last Snapshot Balance ---
                    last_balance_label = Label(
                        text=last_balance_str, size_hint_y=None, height=dp(40),
                        halign="right", valign="middle", color=(0.8, 0.8, 0.8, 1),
                        size_hint_x=0.25
                    )
                    last_balance_label.bind(width=lambda instance, width: setattr(instance, 'text_size', (width, None)))
                    self.account_list_layout.add_widget(last_balance_label)
                    # --- STORE REFERENCE to the label ---
                    self.last_balance_labels[account.id] = last_balance_label


                    # --- Column 3: Current Balance Input ---
                    balance_input = Factory.NumericInput(
                        hint_text="0.00", size_hint_y=None, height=dp(40),
                        halign="right", size_hint_x=0.35
                    )
                    self.account_list_layout.add_widget(balance_input)
                    # Store reference to the input widget
                    self.account_inputs[account.id] = balance_input # Keep this too

        except Exception as e:
            # ... (error handling) ...
            self.snapshot_status_label.text = f"Error loading accounts: {e}"
            print(f"Database error loading accounts: {e}")
            self.account_list_layout.clear_widgets()
            self.account_list_layout.add_widget(Label(text="Error loading. Check logs."))

    # --- MODIFIED: create_new_snapshot ---
    def create_new_snapshot(self):
        if not self.account_inputs:
            self.snapshot_status_label.text = "No accounts loaded or inputs available."
            return

        print("Create Snapshot button pressed - Reading balances from inputs")

        current_balances = {} # Holds {acc_id: balance_float} from inputs
        errors = []
        for acc_id, input_widget in self.account_inputs.items():
            balance_str = input_widget.text.strip()
            try:
                balance = float(balance_str) if balance_str else 0.0
                current_balances[acc_id] = balance
            except ValueError:
                errors.append(
                    f"Invalid balance for account ID {acc_id}: '{balance_str}'. Using 0.0."
                )
                current_balances[acc_id] = 0.0

        if errors:
            print("Input errors found:\n" + "\n".join(errors))
            # Optionally update status label more prominently here

        # Proceed with creating the snapshot
        try:
            with SessionLocal() as db:
                account_ids = list(current_balances.keys())
                if not account_ids:
                    self.snapshot_status_label.text = "No account balances entered."
                    return

                # Optional: Verify accounts still exist
                accounts_in_db = db.query(Account.id).filter(Account.id.in_(account_ids)).count()
                if accounts_in_db != len(account_ids):
                    self.snapshot_status_label.text = "Error: Account mismatch. Reloading UI."
                    print("Account mismatch detected, reloading UI.")
                    self.load_accounts_ui() # Reload might fix inconsistencies
                    return

                # Create the Snapshot record
                new_snapshot = Snapshot(notes="Manual Snapshot via UI")
                db.add(new_snapshot)
                db.flush() # Get the new_snapshot.id

                # Create SnapshotEntry records
                for acc_id, bal in current_balances.items():
                    entry = SnapshotEntry(
                        snapshot_id=new_snapshot.id, account_id=acc_id, balance=bal
                    )
                    db.add(entry)

                db.commit() # Commit snapshot and entries
                timestamp_str = new_snapshot.timestamp.strftime("%Y-%m-%d %H:%M:%S")
                status_msg = f"Snapshot created at {timestamp_str} with {len(current_balances)} entries."
                if errors:
                    status_msg += "\nNote: Some invalid balances were set to 0.0."

                self.snapshot_status_label.text = status_msg
                print(f"Snapshot ID: {new_snapshot.id} created.")

                # --- NEW: Update the 'Last Balance' labels in the UI ---
                print("Updating UI labels with new snapshot balances...")
                for acc_id, new_balance in current_balances.items():
                    if acc_id in self.last_balance_labels:
                        self.last_balance_labels[acc_id].text = f"{new_balance:.2f}"
                    else:
                        print(f"Warning: Could not find last balance label for account ID {acc_id} to update.")

        except Exception as e:
            self.snapshot_status_label.text = f"Error saving snapshot: {e}"
            print(f"Database error during snapshot save: {e}")
