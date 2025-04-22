from kivy.app import App  # Needed for App.get_running_app() in on_touch_down
from kivy.uix.screenmanager import Screen
from kivy.properties import (
    ObjectProperty,
    NumericProperty,
    StringProperty,
    BooleanProperty,
)
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.popup import Popup
from kivy.metrics import dp
from kivy.clock import Clock

from database import SessionLocal, Account, Transaction, SnapshotEntry


class AccountListItem(BoxLayout):
    # Define Kivy properties to hold the data passed from the RecycleView
    # These will automatically link to the keys in your data dictionary
    account_id = NumericProperty(-1)
    account_name = StringProperty("")
    selected = BooleanProperty(False)

    def on_touch_down(self, touch):
        """Handles touch events for this specific list item widget."""
        # Check if the touch coordinates fall within the bounds of this widget
        if self.collide_point(*touch.pos):
            print(
                f"AccountListItem touched: ID {self.account_id}, Name {self.account_name}"
            )
            # Find the running app instance, access its root (ScreenManager),
            # get the target screen, and call the handler method.
            # Pass the data associated with *this specific* widget instance.
            App.get_running_app().root.get_screen(
                "account_management"
            ).handle_selection(self.account_id, self.account_name, self)
            # Return True to indicate we've handled this touch event
            # and it shouldn't be processed further (prevents scrolling while tapping).
            return True
        # If the touch was outside this widget, let the parent handle it
        # (e.g., for scrolling the RecycleView).
        return super().on_touch_down(touch)


class AccountManagementScreen(Screen):
    account_recycle_view = ObjectProperty(None)  # To hold the RecycleView
    status_label = ObjectProperty(None)  # For messages
    selected_account_data = ObjectProperty(None, allownone=True)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def on_enter(self, *args):
        """Called when the screen is displayed."""
        print("Entering Account Management Screen.")
        self.deselect_account()  # Clear selection when entering
        Clock.schedule_once(self._setup_ui, 0)

    def _setup_ui(self, dt):
        if not self.account_recycle_view or not self.status_label:
            print("Error: Account Management UI elements not ready.")
            # Maybe add default text to status_label if it exists
            if self.status_label:
                self.status_label.text = "Error loading UI."
            return
        self.status_label.text = "Manage your accounts."
        self.load_accounts_for_rv()

    def load_accounts_for_rv(self):
        """Loads accounts from DB and prepares data for RecycleView."""
        if not self.account_recycle_view:
            self.status_label.text = "Error: RecycleView not found."
            return

        print("Loading accounts for RecycleView...")
        try:
            with SessionLocal() as db:
                accounts = db.query(Account).order_by(Account.name).all()
                # Data now only needs basic info, selection state is handled by interaction
                self.account_recycle_view.data = [
                    {
                        "account_id": acc.id,
                        "account_name": acc.name,
                        "selected": False,
                    }  # Add 'selected' key
                    for acc in accounts
                ]
                self.status_label.text = f"Loaded {len(accounts)} accounts."
                self.deselect_account()  # Ensure nothing is selected programmatically on load

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
            current_id = item_data["account_id"]
            # Check if this is the item that was clicked
            if current_id == account_id:
                # Toggle selection for this item
                item_data["selected"] = not item_data["selected"]
                if item_data["selected"]:
                    # If this item is now selected, store its data and mark item_selected
                    self.selected_account_data = {
                        "id": account_id,
                        "name": account_name,
                    }
                    self.status_label.text = f"Selected: {account_name}"
                    item_selected = True
                else:
                    # If it was deselected, clear stored data
                    self.deselect_account()  # Use helper to clear status too
            else:
                # Deselect all other items (for single selection)
                item_data["selected"] = False
            new_data.append(item_data)

        # If nothing ended up selected (because the clicked item was deselected)
        if not item_selected:
            self.deselect_account()  # Ensure selected_account_data is cleared

        # Update the RecycleView's data property
        self.account_recycle_view.data = new_data
        # Refreshing the view is often needed after data change
        self.account_recycle_view.refresh_from_data()  # May not be needed if viewclass updates visuals correctly

        return True  # Indicate touch was handled

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
        content = BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(10))
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

        print(f"Attempting to add account: {name}")
        try:
            with SessionLocal() as db:
                # Check if account already exists (optional but good practice)
                exists = (
                    db.query(Account).filter(Account.name == name).first()
                )  # Use Account model
                if exists:
                    self.status_label.text = f"Account '{name}' already exists."
                    print(f"Account '{name}' already exists.")
                    return

                new_account = Account(name=name)  # Create new Account object
                db.add(new_account)
                db.commit()
                print(f"Account '{name}' added successfully.")
                self.status_label.text = f"Account '{name}' added."
                self.load_accounts_for_rv()  # Refresh the list

        except Exception as e:
            db.rollback()  # Rollback on error
            error_msg = f"Error adding account '{name}': {e}"
            self.status_label.text = error_msg
            print(error_msg)

    def open_edit_account_popup(self):
        selected = self.get_selected_account()
        if not selected:
            if self.status_label:
                self.status_label.text = "Select an account to edit."
            return

        account_id = selected["id"]
        account_name = selected["name"]
        print(f"Opening edit popup for Account ID: {account_id}, Name: {account_name}")

        try:  # Add error handling
            content = BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(10))
            popup_label = Label(text=f"Enter new name for '{account_name}':")
            name_input = TextInput(
                text=account_name, multiline=False, hint_text="New Account Name"
            )
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
                    if self.status_label:
                        self.status_label.text = "Account name cannot be empty."
                else:  # Name didn't change or was empty
                    popup.dismiss()

            save_button.bind(on_press=save_edit_action)
            cancel_button.bind(on_press=popup.dismiss)

            popup.open()

        except Exception as e:
            print(f"Error opening Edit Account popup: {e}")
            if self.status_label:
                self.status_label.text = "Error opening edit dialog."

    def edit_account(self, account_id, new_name):
        if not new_name:
            self.status_label.text = "New account name cannot be empty."
            return

        print(f"Attempting to edit account ID {account_id} to '{new_name}'")
        try:
            with SessionLocal() as db:
                # Check if another account with the new name already exists
                exists = (
                    db.query(Account)
                    .filter(Account.name == new_name, Account.id != account_id)
                    .first()
                )
                if exists:
                    self.status_label.text = (
                        f"Another account named '{new_name}' already exists."
                    )
                    print(f"Account '{new_name}' already exists.")
                    return

                account_to_edit = (
                    db.query(Account).filter(Account.id == account_id).first()
                )
                if account_to_edit:
                    account_to_edit.name = new_name
                    db.commit()
                    print(f"Account ID {account_id} updated to '{new_name}'.")
                    self.status_label.text = f"Account '{new_name}' updated."
                    self.load_accounts_for_rv()  # Refresh list with new name
                else:
                    self.status_label.text = (
                        f"Error: Account ID {account_id} not found for editing."
                    )
                    print(f"Account ID {account_id} not found.")

        except Exception as e:
            db.rollback()
            error_msg = f"Error editing account ID {account_id}: {e}"
            self.status_label.text = error_msg
            print(error_msg)

    def confirm_delete_account(self):
        selected = self.get_selected_account()
        if not selected:
            if self.status_label:
                self.status_label.text = "Select an account to delete."
            return

        account_id = selected["id"]
        account_name = selected["name"]
        print(
            f"Opening delete confirmation for Account ID: {account_id}, Name: {account_name}"
        )

        # --- Check dependencies FIRST ---
        dependency_text = self.check_account_dependencies(account_id)

        try:  # Add error handling
            content = BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(10))
            popup = None  # Define popup variable

            if dependency_text:
                # If dependencies exist, show warning and only an OK button
                warning_label = Label(
                    text=f"Cannot delete '{account_name}':\n{dependency_text}",
                    halign="center",
                )
                ok_button = Button(text="OK", size_hint_y=None, height=dp(50))
                content.add_widget(warning_label)
                content.add_widget(ok_button)
                popup = Popup(
                    title="Deletion Prevented", content=content, size_hint=(0.7, 0.4)
                )
                ok_button.bind(on_press=popup.dismiss)
            else:
                # No dependencies, show confirmation
                confirm_label = Label(
                    text=f"Are you sure you want to delete account '{account_name}'?\nThis action cannot be undone.",
                    halign="center",
                )
                button_box = BoxLayout(size_hint_y=None, height=dp(50), spacing=dp(10))
                delete_button = Button(
                    text="Delete", background_color=(1, 0, 0, 1)
                )  # Red button
                cancel_button = Button(text="Cancel")
                button_box.add_widget(delete_button)
                button_box.add_widget(cancel_button)
                content.add_widget(confirm_label)
                content.add_widget(button_box)

                popup = Popup(
                    title="Confirm Deletion", content=content, size_hint=(0.7, 0.4)
                )

                def delete_action(instance):
                    self.delete_account(account_id)  # Call the actual delete method
                    popup.dismiss()

                delete_button.bind(on_press=delete_action)
                cancel_button.bind(on_press=popup.dismiss)

            if popup:  # Check if popup was created
                popup.open()
            else:  # Should not happen unless dependency check failed weirdly
                raise Exception("Popup creation failed unexpectedly.")

        except Exception as e:
            print(f"Error opening Delete Confirmation popup: {e}")
            if self.status_label:
                self.status_label.text = "Error opening delete dialog."

    # check_account_dependencies (Add this method if it's missing or incomplete)
    def check_account_dependencies(self, account_id):
        """Checks if an account has linked transactions or snapshot entries. Returns warning text or None."""
        try:
            with SessionLocal() as db:
                transaction_count = (
                    db.query(Transaction)
                    .filter(Transaction.account_id == account_id)
                    .count()
                )
                snapshot_count = (
                    db.query(SnapshotEntry)
                    .filter(SnapshotEntry.account_id == account_id)
                    .count()
                )
                warnings = []
                if transaction_count > 0:
                    warnings.append(f"{transaction_count} linked transaction(s)")
                if snapshot_count > 0:
                    warnings.append(f"{snapshot_count} linked snapshot entry(s)")

                return "\n".join(warnings) if warnings else None
        except Exception as e:
            print(f"Error checking dependencies for account {account_id}: {e}")
            return f"Error checking dependencies: {e}"  # Return error string

    def delete_account(self, account_id):
        # Dependency check should be done *before* calling this method (in confirm_delete_account)

        print(f"Attempting to delete account ID {account_id}")
        try:
            with SessionLocal() as db:
                # Optional safety re-check (can be removed if confirm_delete_account is reliable)
                # if self.check_account_dependencies(account_id):
                #    print(f"Deletion aborted for account ID {account_id} due to dependencies found unexpectedly.")
                #    if self.status_label: self.status_label.text = "Deletion cancelled: Account has linked data."
                #    return

                account_to_delete = (
                    db.query(Account).filter(Account.id == account_id).first()
                )
                if account_to_delete:
                    account_name = account_to_delete.name  # Get name before deleting
                    db.delete(account_to_delete)
                    db.commit()
                    print(f"Account '{account_name}' (ID: {account_id}) deleted.")
                    if self.status_label:
                        self.status_label.text = f"Account '{account_name}' deleted."
                    self.load_accounts_for_rv()  # Refresh list
                    self.deselect_account()  # Clear selection
                else:
                    if self.status_label:
                        self.status_label.text = (
                            f"Error: Account ID {account_id} not found."
                        )
                    print(f"Account ID {account_id} not found for deletion.")

        except Exception as e:
            # db.rollback() # Handled by SessionLocal context manager
            error_msg = f"Error deleting account ID {account_id}: {e}"
            if self.status_label:
                self.status_label.text = error_msg
            print(error_msg)
