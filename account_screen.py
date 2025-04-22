from kivy.uix.screenmanager import Screen
from kivy.properties import ObjectProperty
from kivy.uix.label import Label
from kivy.factory import Factory
from kivy.metrics import dp
from kivy.clock import Clock

from database import SessionLocal, Account, Snapshot, SnapshotEntry


class AccountsScreen(Screen):
    snapshot_status_label = ObjectProperty(None)
    account_list_layout = ObjectProperty(None)  # Reference to the GridLayout

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Dictionary to store references: {account_id: balance_input_widget}
        self.account_inputs = {}

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
        """Queries DB for accounts and populates the GridLayout."""
        # Ensure layout is ready (should be by the time _setup_ui calls this)
        if not self.account_list_layout:
            print("Error: Account list layout not ready in load_accounts_ui.")
            # Attempting to access self.snapshot_status_label here might also fail if layout isn't ready
            # If snapshot_status_label is available, use it for error message:
            if self.snapshot_status_label:
                self.snapshot_status_label.text = "Internal Error: UI layout missing."
            return

        # Clear existing widgets before adding new ones
        self.account_list_layout.clear_widgets()
        self.account_inputs.clear()  # Clear the references as well

        try:
            with SessionLocal() as db:
                accounts = db.query(Account).order_by(Account.name).all()

                if not accounts:
                    self.account_list_layout.add_widget(
                        Label(text="No accounts found in database.")
                    )
                    return

                # Dynamically create Label and TextInput for each account
                for account in accounts:
                    # Account Name Label
                    name_label = Label(
                        text=account.name,
                        size_hint_y=None,
                        height=dp(40),
                        halign="left",
                        valign="middle",
                        text_size=(
                            self.width * 0.5,
                            None,
                        ),  # Adjust width constraint if needed
                    )
                    self.account_list_layout.add_widget(name_label)

                    # Balance Input TextInput (using the custom NumericInput from kv)
                    balance_input = (
                        Factory.NumericInput(  # Use Factory to create kv defined class
                            hint_text="0.00",
                            size_hint_y=None,
                            height=dp(40),
                            size_hint_x=0.4,  # Match kv layout if needed
                        )
                    )
                    self.account_list_layout.add_widget(balance_input)

                    # Store the reference to the input widget, keyed by account ID
                    self.account_inputs[account.id] = balance_input

        except Exception as e:
            self.snapshot_status_label.text = f"Error loading accounts: {e}"
            print(f"Database error loading accounts: {e}")

    def create_new_snapshot(self):
        if not self.account_inputs:
            self.snapshot_status_label.text = "No accounts loaded or inputs available."
            return

        print("Create Snapshot button pressed - Reading balances from inputs")

        current_balances = {}
        errors = []
        # Read balances from the TextInput widgets stored in self.account_inputs
        for acc_id, input_widget in self.account_inputs.items():
            balance_str = input_widget.text.strip()
            try:
                # Use 0.0 if input is empty, otherwise convert to float
                balance = float(balance_str) if balance_str else 0.0
                current_balances[acc_id] = balance
            except ValueError:
                # Handle cases where input is not a valid number
                errors.append(
                    f"Invalid balance for account ID {acc_id}: '{balance_str}'. Using 0.0."
                )
                current_balances[acc_id] = 0.0  # Default to 0 on error

        if errors:
            print("Input errors found:\n" + "\n".join(errors))
            # Optionally show a more prominent error to the user
            # self.snapshot_status_label.text = "Warning: Invalid balance input detected. Used 0.0."
            # return # Or decide to proceed with 0.0 values

        # Proceed with creating the snapshot using the collected balances
        try:
            with SessionLocal() as db:
                # Check if we actually have accounts associated with the inputs
                account_ids = list(current_balances.keys())
                if not account_ids:
                    self.snapshot_status_label.text = "No account balances entered."
                    return

                # Verify accounts still exist (optional, good practice)
                accounts_in_db = (
                    db.query(Account.id).filter(Account.id.in_(account_ids)).count()
                )
                if accounts_in_db != len(account_ids):
                    self.snapshot_status_label.text = (
                        "Error: Some accounts seem missing. Reloading."
                    )
                    print("Account mismatch detected, reloading UI.")
                    self.load_accounts_ui()  # Reload might fix inconsistencies
                    return

                # Create the Snapshot record
                new_snapshot = Snapshot(
                    notes="Manual Snapshot via UI"
                )  # Timestamp added automatically
                db.add(new_snapshot)
                db.flush()  # Get the new_snapshot.id

                # Create SnapshotEntry records for each account balance
                for acc_id, bal in current_balances.items():
                    entry = SnapshotEntry(
                        snapshot_id=new_snapshot.id, account_id=acc_id, balance=bal
                    )
                    db.add(entry)

                db.commit()
                timestamp_str = new_snapshot.timestamp.strftime("%Y-%m-%d %H:%M:%S")
                status_msg = f"Snapshot created at {timestamp_str} with {len(current_balances)} entries."
                if errors:
                    status_msg += "\nNote: Some invalid balances were set to 0.0."
                self.snapshot_status_label.text = status_msg
                print(f"Snapshot ID: {new_snapshot.id} created.")

        except Exception as e:
            self.snapshot_status_label.text = f"Error saving snapshot: {e}"
            print(f"Database error during snapshot save: {e}")
            # Consider db.rollback() - handled by 'with SessionLocal()' context manager
