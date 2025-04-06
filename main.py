import os
import csv # Using standard csv module for this example
import datetime # To handle dates
from kivy.uix.boxlayout import BoxLayout
from kivy.properties import NumericProperty, StringProperty, BooleanProperty
from kivy.app import App # Needed to access the running app instance
from kivy.app import App
from kivy.uix.textinput import TextInput
from kivy.uix.screenmanager import ScreenManager, Screen 
from kivy.uix.popup import Popup
from kivy.uix.filechooser import FileChooserListView
from kivy.properties import ObjectProperty, StringProperty
from kivy.lang import Builder
from kivy.metrics import dp
from kivy.uix.button import Button
from kivy.clock import Clock
from kivy.uix.label import Label
from kivy.factory import Factory

# --- Database Imports ---
try:
    from database import SessionLocal, init_db, Account, Transaction, Category, Snapshot, SnapshotEntry
    db_available = True
except ImportError as e:
    print(f"Database modules not found: {e}. Database functionality will be disabled.")
    db_available = False
    # Define dummy classes if DB is not available to prevent NameErrors later
    class SessionLocal: pass
    class Account: pass
    class Transaction: pass
    class Category: pass
    class Snapshot: pass
    class SnapshotEntry: pass
    def init_db(): print("Database unavailable, skipping init.")

# Load the kv file explicitly
# Builder.load_file('budget.kv')

class AccountListItem(BoxLayout):
    # Define Kivy properties to hold the data passed from the RecycleView
    # These will automatically link to the keys in your data dictionary
    account_id = NumericProperty(-1)
    account_name = StringProperty('')
    selected = BooleanProperty(False)

    def on_touch_down(self, touch):
        """ Handles touch events for this specific list item widget. """
        # Check if the touch coordinates fall within the bounds of this widget
        if self.collide_point(*touch.pos):
            print(f"AccountListItem touched: ID {self.account_id}, Name {self.account_name}")
            # Find the running app instance, access its root (ScreenManager),
            # get the target screen, and call the handler method.
            # Pass the data associated with *this specific* widget instance.
            App.get_running_app().root.get_screen('account_management').handle_selection(
                self.account_id, self.account_name, self
            )
            # Return True to indicate we've handled this touch event
            # and it shouldn't be processed further (prevents scrolling while tapping).
            return True
        # If the touch was outside this widget, let the parent handle it
        # (e.g., for scrolling the RecycleView).
        return super().on_touch_down(touch)

# --- Screen Definitions ---

# --- Add this near other Screen definitions ---
class AccountManagementScreen(Screen):
    account_recycle_view = ObjectProperty(None) # To hold the RecycleView
    status_label = ObjectProperty(None)        # For messages
    selected_account_data = ObjectProperty(None, allownone=True)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def on_enter(self, *args):
        """Called when the screen is displayed."""
        print("Entering Account Management Screen.")
        self.deselect_account() # Clear selection when entering
        Clock.schedule_once(self._setup_ui, 0)

    def _setup_ui(self, dt):
        if not self.account_recycle_view or not self.status_label:
             print("Error: Account Management UI elements not ready.")
             # Maybe add default text to status_label if it exists
             if self.status_label: self.status_label.text = "Error loading UI."
             return
        self.status_label.text = "Manage your accounts."
        self.load_accounts_for_rv()

    def load_accounts_for_rv(self):
        """Loads accounts from DB and prepares data for RecycleView."""
        if not db_available:
            self.status_label.text = "Database unavailable."
            return
        if not self.account_recycle_view:
            self.status_label.text = "Error: RecycleView not found."
            return

        print("Loading accounts for RecycleView...")
        try:
            with SessionLocal() as db:
                accounts = db.query(Account).order_by(Account.name).all()
                # Data now only needs basic info, selection state is handled by interaction
                self.account_recycle_view.data = [
                    {'account_id': acc.id, 'account_name': acc.name, 'selected': False} # Add 'selected' key
                    for acc in accounts
                ]
                self.status_label.text = f"Loaded {len(accounts)} accounts."
                self.deselect_account() # Ensure nothing is selected programmatically on load

        except Exception as e:
            error_msg = f"Error loading accounts: {e}"
            self.status_label.text = error_msg
            print(error_msg)

        # Refresh the view after updating data
        self.account_recycle_view.refresh_from_data()

    def handle_selection(self, account_id, account_name, view_instance):
        """Manages selecting/deselecting items in the RecycleView."""
        print(f"Selection attempt on ID: {account_id}, Name: {account_name}")

        # Update the underlying data list to reflect selection changes
        new_data = []
        item_selected = False
        for item_data in self.account_recycle_view.data:
            current_id = item_data['account_id']
            # Check if this is the item that was clicked
            if current_id == account_id:
                # Toggle selection for this item
                item_data['selected'] = not item_data['selected']
                if item_data['selected']:
                    # If this item is now selected, store its data and mark item_selected
                    self.selected_account_data = {'id': account_id, 'name': account_name}
                    self.status_label.text = f"Selected: {account_name}"
                    item_selected = True
                else:
                    # If it was deselected, clear stored data
                    self.deselect_account() # Use helper to clear status too
            else:
                # Deselect all other items (for single selection)
                item_data['selected'] = False
            new_data.append(item_data)

        # If nothing ended up selected (because the clicked item was deselected)
        if not item_selected:
             self.deselect_account() # Ensure selected_account_data is cleared

        # Update the RecycleView's data property
        self.account_recycle_view.data = new_data
        # Refreshing the view is often needed after data change
        self.account_recycle_view.refresh_from_data() # May not be needed if viewclass updates visuals correctly

        return True # Indicate touch was handled
    
    def deselect_account(self):
        """Helper to clear selection state."""
        self.selected_account_data = None
        if self.status_label and not self.status_label.text.startswith("Error"):
             self.status_label.text = "Manage your accounts. Select one to edit/delete."
         # You might also iterate through data and set 'selected' to False if needed,
         # though handle_selection should manage this for single-select.
    
    def get_selected_account(self):
        """Returns the data dict of the selected account or None."""
        # Now simply return the stored data
        return self.selected_account_data
    
    def open_add_account_popup(self):
        """Opens a popup to add a new account."""
        # --- Basic Popup Implementation ---
        content = BoxLayout(orientation='vertical', padding=dp(10), spacing=dp(10))
        popup_label = Label(text="Enter new account name:")
        name_input = TextInput(multiline=False, hint_text="Account Name")
        button_box = BoxLayout(size_hint_y=None, height=dp(50), spacing=dp(10))
        save_button = Button(text="Save")
        cancel_button = Button(text="Cancel")
        button_box.add_widget(save_button)
        button_box.add_widget(cancel_button)

        content.add_widget(popup_label)
        content.add_widget(name_input)
        content.add_widget(button_box)

        popup = Popup(title="Add Account", content=content, size_hint=(0.7, 0.4))

        # --- Button Actions ---
        def save_action(instance):
            account_name = name_input.text.strip()
            if account_name:
                self.add_account(account_name)
                popup.dismiss()
            else:
                # Optional: Add feedback in the popup or main screen
                print("Account name cannot be empty.")
                self.status_label.text = "Account name cannot be empty."


        save_button.bind(on_press=save_action)
        cancel_button.bind(on_press=popup.dismiss)

        popup.open()

    def add_account(self, name):
        """Adds a new account to the database."""
        if not db_available:
            self.status_label.text = "Database unavailable. Cannot add account."
            return

        print(f"Attempting to add account: {name}")
        try:
            with SessionLocal() as db:
                # Check if account already exists (optional but good practice)
                exists = db.query(Account).filter(Account.name == name).first() # Use Account model
                if exists:
                    self.status_label.text = f"Account '{name}' already exists."
                    print(f"Account '{name}' already exists.")
                    return

                new_account = Account(name=name) # Create new Account object
                db.add(new_account)
                db.commit()
                print(f"Account '{name}' added successfully.")
                self.status_label.text = f"Account '{name}' added."
                self.load_accounts_for_rv() # Refresh the list

        except Exception as e:
            db.rollback() # Rollback on error
            error_msg = f"Error adding account '{name}': {e}"
            self.status_label.text = error_msg
            print(error_msg)

    def open_edit_account_popup(self):
         selected = self.get_selected_account()
         if not selected:
              if self.status_label: self.status_label.text = "Select an account to edit."
              return

         account_id = selected['id']
         account_name = selected['name']
         print(f"Opening edit popup for Account ID: {account_id}, Name: {account_name}")

         try: # Add error handling
             content = BoxLayout(orientation='vertical', padding=dp(10), spacing=dp(10))
             popup_label = Label(text=f"Enter new name for '{account_name}':")
             name_input = TextInput(text=account_name, multiline=False, hint_text="New Account Name")
             button_box = BoxLayout(size_hint_y=None, height=dp(50), spacing=dp(10))
             save_button = Button(text="Save Changes")
             cancel_button = Button(text="Cancel")
             button_box.add_widget(save_button)
             button_box.add_widget(cancel_button)

             content.add_widget(popup_label)
             content.add_widget(name_input)
             content.add_widget(button_box)

             popup = Popup(title="Edit Account", content=content, size_hint=(0.7, 0.4))

             def save_edit_action(instance):
                 new_name = name_input.text.strip()
                 if new_name and new_name != account_name:
                     self.edit_account(account_id, new_name)
                     popup.dismiss()
                 elif not new_name:
                     if self.status_label: self.status_label.text = "Account name cannot be empty."
                 else: # Name didn't change or was empty
                     popup.dismiss()

             save_button.bind(on_press=save_edit_action)
             cancel_button.bind(on_press=popup.dismiss)

             popup.open()

         except Exception as e:
             print(f"Error opening Edit Account popup: {e}")
             if self.status_label: self.status_label.text = "Error opening edit dialog."

    def edit_account(self, account_id, new_name):
        if not db_available:
            self.status_label.text = "Database unavailable. Cannot edit account."
            return
        if not new_name:
            self.status_label.text = "New account name cannot be empty."
            return

        print(f"Attempting to edit account ID {account_id} to '{new_name}'")
        try:
            with SessionLocal() as db:
                 # Check if another account with the new name already exists
                exists = db.query(Account).filter(Account.name == new_name, Account.id != account_id).first()
                if exists:
                    self.status_label.text = f"Another account named '{new_name}' already exists."
                    print(f"Account '{new_name}' already exists.")
                    return

                account_to_edit = db.query(Account).filter(Account.id == account_id).first()
                if account_to_edit:
                    account_to_edit.name = new_name
                    db.commit()
                    print(f"Account ID {account_id} updated to '{new_name}'.")
                    self.status_label.text = f"Account '{new_name}' updated."
                    self.load_accounts_for_rv() # Refresh list with new name
                else:
                    self.status_label.text = f"Error: Account ID {account_id} not found for editing."
                    print(f"Account ID {account_id} not found.")

        except Exception as e:
            db.rollback()
            error_msg = f"Error editing account ID {account_id}: {e}"
            self.status_label.text = error_msg
            print(error_msg)

    def confirm_delete_account(self):
         selected = self.get_selected_account()
         if not selected:
             if self.status_label: self.status_label.text = "Select an account to delete."
             return

         account_id = selected['id']
         account_name = selected['name']
         print(f"Opening delete confirmation for Account ID: {account_id}, Name: {account_name}")

         # --- Check dependencies FIRST ---
         dependency_text = self.check_account_dependencies(account_id)

         try: # Add error handling
             content = BoxLayout(orientation='vertical', padding=dp(10), spacing=dp(10))
             popup = None # Define popup variable

             if dependency_text:
                 # If dependencies exist, show warning and only an OK button
                 warning_label = Label(text=f"Cannot delete '{account_name}':\n{dependency_text}", halign='center')
                 ok_button = Button(text="OK", size_hint_y=None, height=dp(50))
                 content.add_widget(warning_label)
                 content.add_widget(ok_button)
                 popup = Popup(title="Deletion Prevented", content=content, size_hint=(0.7, 0.4))
                 ok_button.bind(on_press=popup.dismiss)
             else:
                 # No dependencies, show confirmation
                 confirm_label = Label(text=f"Are you sure you want to delete account '{account_name}'?\nThis action cannot be undone.", halign='center')
                 button_box = BoxLayout(size_hint_y=None, height=dp(50), spacing=dp(10))
                 delete_button = Button(text="Delete", background_color=(1, 0, 0, 1)) # Red button
                 cancel_button = Button(text="Cancel")
                 button_box.add_widget(delete_button)
                 button_box.add_widget(cancel_button)
                 content.add_widget(confirm_label)
                 content.add_widget(button_box)

                 popup = Popup(title="Confirm Deletion", content=content, size_hint=(0.7, 0.4))

                 def delete_action(instance):
                     self.delete_account(account_id) # Call the actual delete method
                     popup.dismiss()

                 delete_button.bind(on_press=delete_action)
                 cancel_button.bind(on_press=popup.dismiss)

             if popup: # Check if popup was created
                 popup.open()
             else: # Should not happen unless dependency check failed weirdly
                 raise Exception("Popup creation failed unexpectedly.")

         except Exception as e:
             print(f"Error opening Delete Confirmation popup: {e}")
             if self.status_label: self.status_label.text = "Error opening delete dialog."


    # check_account_dependencies (Add this method if it's missing or incomplete)
    def check_account_dependencies(self, account_id):
        """Checks if an account has linked transactions or snapshot entries. Returns warning text or None."""
        if not db_available:
            return "Database unavailable."
        try:
            with SessionLocal() as db:
                transaction_count = db.query(Transaction).filter(Transaction.account_id == account_id).count()
                snapshot_count = db.query(SnapshotEntry).filter(SnapshotEntry.account_id == account_id).count()
                warnings = []
                if transaction_count > 0:
                    warnings.append(f"{transaction_count} linked transaction(s)")
                if snapshot_count > 0:
                    warnings.append(f"{snapshot_count} linked snapshot entry(s)")

                return "\n".join(warnings) if warnings else None
        except Exception as e:
            print(f"Error checking dependencies for account {account_id}: {e}")
            return f"Error checking dependencies: {e}" # Return error string

    def delete_account(self, account_id):
        # Dependency check should be done *before* calling this method (in confirm_delete_account)
        if not db_available:
            if self.status_label: self.status_label.text = "Database unavailable."
            return

        print(f"Attempting to delete account ID {account_id}")
        try:
            with SessionLocal() as db:
                 # Optional safety re-check (can be removed if confirm_delete_account is reliable)
                 # if self.check_account_dependencies(account_id):
                 #    print(f"Deletion aborted for account ID {account_id} due to dependencies found unexpectedly.")
                 #    if self.status_label: self.status_label.text = "Deletion cancelled: Account has linked data."
                 #    return

                account_to_delete = db.query(Account).filter(Account.id == account_id).first()
                if account_to_delete:
                    account_name = account_to_delete.name # Get name before deleting
                    db.delete(account_to_delete)
                    db.commit()
                    print(f"Account '{account_name}' (ID: {account_id}) deleted.")
                    if self.status_label: self.status_label.text = f"Account '{account_name}' deleted."
                    self.load_accounts_for_rv() # Refresh list
                    self.deselect_account() # Clear selection
                else:
                    if self.status_label: self.status_label.text = f"Error: Account ID {account_id} not found."
                    print(f"Account ID {account_id} not found for deletion.")

        except Exception as e:
            # db.rollback() # Handled by SessionLocal context manager
            error_msg = f"Error deleting account ID {account_id}: {e}"
            if self.status_label: self.status_label.text = error_msg
            print(error_msg)

class AccountsScreen(Screen):
    snapshot_status_label = ObjectProperty(None)
    account_list_layout = ObjectProperty(None) # Reference to the GridLayout

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Dictionary to store references: {account_id: balance_input_widget}
        self.account_inputs = {}

    def on_enter(self, *args):
        """Called when the screen is displayed. Schedule the UI setup."""
        # Schedule the actual setup for the next frame to ensure widgets are ready
        Clock.schedule_once(self._setup_ui, 0) # 0 schedules for the very next frame

    def _setup_ui(self, dt): # dt is the time delta passed by Clock
        """This method runs after on_enter, when widgets should be bound."""
        print("Entering Accounts Screen (_setup_ui). Loading accounts...")

        # Defensive check (optional but good practice)
        if not self.snapshot_status_label or not self.account_list_layout:
             print("Error: UI elements not ready even after scheduling. Aborting setup.")
             # You could try rescheduling again: Clock.schedule_once(self._setup_ui, 0.1)
             return

        self.snapshot_status_label.text = 'Enter current balances above.' # Reset status
        self.load_accounts_ui() # Now load the accounts

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

        if not db_available:
            self.snapshot_status_label.text = "Database connection failed."
            return

        # Clear existing widgets before adding new ones
        self.account_list_layout.clear_widgets()
        self.account_inputs.clear() # Clear the references as well

        try:
            with SessionLocal() as db:
                accounts = db.query(Account).order_by(Account.name).all()

                if not accounts:
                    self.account_list_layout.add_widget(Label(text="No accounts found in database."))
                    return

                # Dynamically create Label and TextInput for each account
                for account in accounts:
                    # Account Name Label
                    name_label = Label(
                        text=account.name,
                        size_hint_y=None,
                        height=dp(40),
                        halign='left',
                        valign='middle',
                        text_size=(self.width*0.5, None) # Adjust width constraint if needed
                    )
                    self.account_list_layout.add_widget(name_label)

                    # Balance Input TextInput (using the custom NumericInput from kv)
                    balance_input = Factory.NumericInput( # Use Factory to create kv defined class
                        hint_text='0.00',
                        size_hint_y=None,
                        height=dp(40),
                        size_hint_x=0.4 # Match kv layout if needed
                    )
                    self.account_list_layout.add_widget(balance_input)

                    # Store the reference to the input widget, keyed by account ID
                    self.account_inputs[account.id] = balance_input

        except Exception as e:
            self.snapshot_status_label.text = f"Error loading accounts: {e}"
            print(f"Database error loading accounts: {e}")


    def create_new_snapshot(self):
        if not db_available:
            self.snapshot_status_label.text = "Cannot create snapshot: Database unavailable."
            return
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
                errors.append(f"Invalid balance for account ID {acc_id}: '{balance_str}'. Using 0.0.")
                current_balances[acc_id] = 0.0 # Default to 0 on error

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
                accounts_in_db = db.query(Account.id).filter(Account.id.in_(account_ids)).count()
                if accounts_in_db != len(account_ids):
                    self.snapshot_status_label.text = "Error: Some accounts seem missing. Reloading."
                    print("Account mismatch detected, reloading UI.")
                    self.load_accounts_ui() # Reload might fix inconsistencies
                    return

                # Create the Snapshot record
                new_snapshot = Snapshot(notes="Manual Snapshot via UI") # Timestamp added automatically
                db.add(new_snapshot)
                db.flush() # Get the new_snapshot.id

                # Create SnapshotEntry records for each account balance
                for acc_id, bal in current_balances.items():
                    entry = SnapshotEntry(
                        snapshot_id=new_snapshot.id,
                        account_id=acc_id,
                        balance=bal
                    )
                    db.add(entry)

                db.commit()
                timestamp_str = new_snapshot.timestamp.strftime('%Y-%m-%d %H:%M:%S')
                status_msg = f"Snapshot created at {timestamp_str} with {len(current_balances)} entries."
                if errors:
                    status_msg += "\nNote: Some invalid balances were set to 0.0."
                self.snapshot_status_label.text = status_msg
                print(f"Snapshot ID: {new_snapshot.id} created.")

        except Exception as e:
            self.snapshot_status_label.text = f"Error saving snapshot: {e}"
            print(f"Database error during snapshot save: {e}")
            # Consider db.rollback() - handled by 'with SessionLocal()' context manager


class BudgetScreen(Screen):
    transaction_list_label = ObjectProperty(None)
    filechooser_popup = ObjectProperty(None)

    def on_enter(self, *args):
        """Called when the screen is displayed."""
        print("Entering Budget Screen. Loading transactions...")
        # Schedule UI update similar to AccountsScreen to ensure label is ready
        Clock.schedule_once(self._setup_ui, 0)

    def _setup_ui(self, dt):
        """Runs after on_enter, ensures widgets are ready."""
        if not self.transaction_list_label:
            print("Error: BudgetScreen UI elements not ready. Aborting setup.")
            return
        self.update_transaction_display() # Initial load attempt

    def show_import_dialog(self):
        if not db_available:
            # Defensive check if label isn't ready yet (though _setup_ui should handle it)
            if self.transaction_list_label:
                 self.transaction_list_label.text = "Cannot import: Database unavailable."
            else:
                 print("Cannot import: Database unavailable and label not ready.")
            return
        # ... (Dialog creation code remains the same) ...
        content = BoxLayout(orientation='vertical', spacing=dp(5))
        filechooser = FileChooserListView(size_hint_y=0.8)
        content.add_widget(filechooser)

        button_box = BoxLayout(size_hint_y=0.1, height=dp(50), spacing=dp(5))
        load_button = Button(text='Load')
        cancel_button = Button(text='Cancel')
        button_box.add_widget(load_button)
        button_box.add_widget(cancel_button)
        content.add_widget(button_box)

        self.filechooser_popup = Popup(title="Import CSV File",
                                       content=content,
                                       size_hint=(0.9, 0.9))

        load_button.bind(on_press=lambda x: self.import_csv(filechooser.path, filechooser.selection))
        cancel_button.bind(on_press=self.filechooser_popup.dismiss)

        self.filechooser_popup.open()

    def import_csv(self, path, selection):
        if not db_available:
            print("Import cancelled: Database unavailable.")
            self.filechooser_popup.dismiss()
            return
        if not selection:
            print("No file selected.")
            self.filechooser_popup.dismiss()
            return

        file_path = os.path.join(path, selection[0])
        print(f"Attempting to import CSV: {file_path}")

        imported_count = 0
        skipped_count = 0
        error_rows = [] # Store rows that caused errors

        try:
            with SessionLocal() as db:
                # --- Get default account and 'Uncategorized' category ---
                default_account = db.query(Account).filter(Account.name == "Cash").first()
                if not default_account:
                    msg = "Error: Default 'Cash' account missing."
                    print(msg)
                    self.transaction_list_label.text = msg
                    self.filechooser_popup.dismiss()
                    return

                uncategorized_cat = db.query(Category).filter(Category.name == "Uncategorized").first()
                if not uncategorized_cat:
                    msg = "Error: 'Uncategorized' category missing."
                    print(msg)
                    self.transaction_list_label.text = msg
                    self.filechooser_popup.dismiss()
                    return

                # --- Cache for Categories found/created during this import ---
                # Stores {'csv_category_name': category_db_object}
                category_cache = {"Uncategorized": uncategorized_cat} # Pre-populate

                with open(file_path, mode='r', encoding='utf-8-sig') as infile:
                    reader = csv.reader(infile, delimiter=',')
                    try:
                        header = next(reader) # Read header row
                    except StopIteration:
                        self.transaction_list_label.text = "Error: CSV file is empty."
                        self.filechooser_popup.dismiss()
                        return
                    print(f"CSV Header: {header}")

                    # --- Define column indices based on YOUR header ---
                    # Header: ['Transaction Date', 'Post Date', 'Description', 'Category', 'Type', 'Amount', 'Memo']
                    try:
                        # Use header.index() for robustness against column reordering
                        date_col_idx = header.index('Transaction Date') # Was 0
                        desc_col_idx = header.index('Description')      # Was 2
                        cat_col_idx = header.index('Category')         # Was 3
                        amount_col_idx = header.index('Amount')         # Was 5
                        # type_col_idx = header.index('Type') # If needed later (index 4)
                    except ValueError as e:
                        msg = f"Error: Missing expected column in CSV header: {e}"
                        print(msg)
                        self.transaction_list_label.text = msg
                        self.filechooser_popup.dismiss()
                        return

                    # Minimum required columns check (optional but good)
                    min_cols = max(date_col_idx, desc_col_idx, cat_col_idx, amount_col_idx) + 1

                    for i, row in enumerate(reader, start=2): # Start count from row 2
                        try:
                            # Basic validation
                            if len(row) < min_cols:
                                print(f"Skipping row {i}, too few columns: {row}")
                                skipped_count += 1
                                error_rows.append((i, row, "Too few columns"))
                                continue

                            # Extract and clean data
                            date_str = row[date_col_idx].strip()
                            description = row[desc_col_idx].strip()
                            category_name_csv = row[cat_col_idx].strip()
                            amount_str = row[amount_col_idx].strip().replace('$', '').replace(',', '') # Clean amount

                            # --- Data Validation & Parsing ---
                            # Validate required fields are not empty
                            if not date_str or not description or not amount_str:
                                print(f"Skipping row {i}, missing required data (Date/Desc/Amount): {row}")
                                skipped_count += 1
                                error_rows.append((i, row, "Missing required data"))
                                continue

                            # Parse Date
                            # *** ADJUST THE FORMAT ('%m/%d/%Y') IF YOUR CSV USES A DIFFERENT ONE ***
                            # Examples: '%Y-%m-%d', '%m/%d/%y' (2-digit year), '%d-%b-%Y' (e.g., 26-Mar-2025)
                            try:
                                trans_date = datetime.datetime.strptime(date_str, '%m/%d/%Y').date()
                            except ValueError:
                                print(f"Skipping row {i}, invalid date format: '{date_str}'. Expected MM/DD/YYYY. Row: {row}")
                                skipped_count += 1
                                error_rows.append((i, row, f"Invalid date format: {date_str}"))
                                continue

                            # Parse Amount
                            # *** ASSUMPTION: Amount column uses negative for expenses, positive for income ***
                            # If not, you might need to use the 'Type' column (index 4) to adjust the sign.
                            try:
                                trans_amount = float(amount_str)
                            except ValueError:
                                print(f"Skipping row {i}, invalid amount format: '{amount_str}'. Row: {row}")
                                skipped_count += 1
                                error_rows.append((i, row, f"Invalid amount format: {amount_str}"))
                                continue

                            # --- Get or Create Category ---
                            target_category = None
                            if not category_name_csv: # Handle empty category field
                                target_category = uncategorized_cat
                            elif category_name_csv in category_cache: # Check cache first
                                target_category = category_cache[category_name_csv]
                            else:
                                # Try finding category in DB
                                category_obj = db.query(Category).filter(Category.name == category_name_csv).first()
                                if category_obj:
                                    target_category = category_obj
                                else:
                                    # Create new category if not found
                                    print(f"Creating new category: '{category_name_csv}' from row {i}")
                                    new_cat = Category(name=category_name_csv)
                                    db.add(new_cat)
                                    # Flush to get the ID without full commit, allows rollback on later error
                                    db.flush()
                                    target_category = new_cat
                                # Add to cache whether found or created
                                category_cache[category_name_csv] = target_category

                            # Defensive check (should always have a category by now)
                            if not target_category:
                                print(f"Error: Failed to assign category for row {i}. Using Uncategorized. Row: {row}")
                                target_category = uncategorized_cat


                            # --- Create Transaction object ---
                            new_trans = Transaction(
                                date=trans_date,
                                description=description,
                                amount=trans_amount,
                                account_id=default_account.id, # Still using default account
                                category_id=target_category.id # Use found/created category ID
                                # notes=row[memo_col_idx].strip() if len(row) > memo_col_idx else None # Optional: Add Memo
                            )
                            db.add(new_trans)
                            imported_count += 1

                        except Exception as e_row:
                            # Catch unexpected errors during row processing
                            print(f"Skipping row {i} due to unexpected error: {e_row}. Row: {row}")
                            skipped_count += 1
                            error_rows.append((i, row, f"Unexpected error: {e_row}"))
                            # Optional: Rollback the specific row's changes if needed,
                            # but SessionLocal handles rollback on context exit if commit fails.

                # --- Commit all successfully processed transactions ---
                db.commit()
                status_msg = f"Import complete from '{os.path.basename(file_path)}'.\n"
                status_msg += f"Successfully imported: {imported_count} transactions.\n"
                if skipped_count > 0:
                    status_msg += f"Skipped: {skipped_count} rows due to errors (see console/log)."
                    # You could print error_rows details here if desired
                    print("\n--- Rows with Import Errors ---")
                    for row_num, row_data, reason in error_rows:
                         print(f"Row {row_num}: {reason} - Data: {row_data}")
                    print("-----------------------------\n")
                self.transaction_list_label.text = status_msg
                print(status_msg)
                self.update_transaction_display() # Refresh display

        except FileNotFoundError:
            msg = f"Error: File not found at {file_path}"
            print(msg)
            self.transaction_list_label.text = msg
        except UnicodeDecodeError:
            msg = f"Error: Could not decode file {os.path.basename(file_path)}. Try saving it as UTF-8."
            print(msg)
            self.transaction_list_label.text = msg
        except Exception as e:
            # Catch broader errors during file open or commit
            msg = f"Error during CSV import process: {e}"
            print(msg)
            self.transaction_list_label.text = msg
            # db.rollback() # Handled by SessionLocal context manager on error before commit

        # Ensure popup closes even if errors occurred before commit
        if self.filechooser_popup:
            self.filechooser_popup.dismiss()

    def update_transaction_display(self):
        """Loads transactions from DB and updates the label (placeholder)."""
        if not db_available:
            if self.transaction_list_label:
                self.transaction_list_label.text = "Database unavailable."
            return
        if not self.transaction_list_label:
            print("Cannot update transaction display: Label not ready.")
            return

        try:
            with SessionLocal() as db:
                recent_transactions = db.query(Transaction).order_by(Transaction.date.desc()).limit(40).all() # Show more

                if not recent_transactions:
                    # Check if text indicates a recent import or error
                    current_text = self.transaction_list_label.text
                    if "Import complete" not in current_text and \
                       "Error" not in current_text and \
                       "No transactions found" not in current_text:
                        self.transaction_list_label.text = 'No transactions found.\nImport a CSV file.'
                    # else: keep the import status/error message
                    return

                # --- Format for display (Still placeholder - Needs RecycleView!) ---
                display_text = "Recent Transactions:\n"
                display_text += "{:<11} | {:<30} | {:>9} | {:<15} | {:<15}\n".format(
                    "Date", "Description", "Amount", "Category", "Account")
                display_text += "-"*80 + "\n" # Separator

                for t in recent_transactions:
                    # Use db.get for potentially better performance than querying in loop
                    acc = db.get(Account, t.account_id)
                    cat = db.get(Category, t.category_id)
                    acc_name = acc.name if acc else "N/A"
                    cat_name = cat.name if cat else "Uncategorized" # Default if category missing

                    display_text += "{:<11} | {:<30} | {:>9.2f} | {:<15} | {:<15}\n".format(
                        str(t.date),
                        (t.description[:28] + '..') if len(t.description) > 30 else t.description,
                        t.amount,
                        (cat_name[:13] + '..') if len(cat_name) > 15 else cat_name,
                        (acc_name[:13] + '..') if len(acc_name) > 15 else acc_name
                    )

                self.transaction_list_label.text = display_text

        except Exception as e:
            print(f"Error loading transactions from DB: {e}")
            self.transaction_list_label.text = f"Error loading transactions: {e}"


# --- Screen Manager ---
class MyScreenManager(ScreenManager):
    pass

# --- Main App Class ---
class BudgetApp(App):
    def build(self):
        if db_available:
            init_db() # Create database tables if they don't exist
        sm = MyScreenManager()
        return sm

    # Optional: Add on_stop method to clean up resources if needed
    # def on_stop(self):
    #     print("Budget App stopping.")
        # Add any cleanup here

# --- Run the App ---
if __name__ == '__main__':
    BudgetApp().run()