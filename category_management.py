from kivy.app import App
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.properties import (
    NumericProperty,
    StringProperty,
    BooleanProperty,
    ObjectProperty,
)
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.screenmanager import Screen
from kivy.uix.textinput import TextInput

from database import SessionLocal, Category, Transaction


class CategoryListItem(BoxLayout):
    category_id = NumericProperty(-1)
    category_name = StringProperty("")
    selected = BooleanProperty(False)

    def on_touch_down(self, touch):
        """Handles touch events for category list item."""
        if self.collide_point(*touch.pos):
            print(
                f"CategoryListItem touched: ID {self.category_id}, Name {self.category_name}"
            )
            # Target the 'category_management' screen and its handler
            App.get_running_app().root.get_screen(
                "category_management"
            ).handle_selection(self.category_id, self.category_name, self)
            return True
        return super().on_touch_down(touch)


class CategoryManagementScreen(Screen):
    category_recycle_view = ObjectProperty(None)  # Adapted name
    status_label = ObjectProperty(None)  # Same name is fine
    selected_category_data = ObjectProperty(None, allownone=True)  # Adapted name

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def on_enter(self, *args):
        """Called when the screen is displayed."""
        print("Entering Category Management Screen.")
        self.deselect_category()  # Clear selection when entering
        Clock.schedule_once(self._setup_ui, 0)

    def _setup_ui(self, dt):
        if not self.category_recycle_view or not self.status_label:
            print("Error: Category Management UI elements not ready.")
            if self.status_label:
                self.status_label.text = "Error loading UI."
            return
        self.status_label.text = "Manage your categories."
        self.load_categories_for_rv()  # Call category loader

    def load_categories_for_rv(self):
        """Loads categories from DB and prepares data for RecycleView."""
        if not self.category_recycle_view:
            self.status_label.text = "Error: RecycleView not found."
            return

        print("Loading categories for RecycleView...")
        try:
            with SessionLocal() as db:
                # Query Category model
                categories = db.query(Category).order_by(Category.name).all()
                # Adapt data dictionary keys
                self.category_recycle_view.data = [
                    {
                        "category_id": cat.id,
                        "category_name": cat.name,
                        "selected": False,
                    }
                    for cat in categories
                ]
                self.status_label.text = f"Loaded {len(categories)} categories."
                self.deselect_category()

        except Exception as e:
            error_msg = f"Error loading categories: {e}"
            self.status_label.text = error_msg
            print(error_msg)

        self.category_recycle_view.refresh_from_data()

    def handle_selection(self, category_id, category_name, view_instance):
        """Manages selecting/deselecting category items in the RecycleView."""
        print(f"Selection attempt on Category ID: {category_id}, Name: {category_name}")

        new_data = []
        item_selected = False
        # Use the correct recycle view property
        for item_data in self.category_recycle_view.data:
            current_id = item_data["category_id"]  # Use correct key
            if current_id == category_id:
                item_data["selected"] = not item_data["selected"]
                if item_data["selected"]:
                    # Store selected category data
                    self.selected_category_data = {
                        "id": category_id,
                        "name": category_name,
                    }
                    self.status_label.text = f"Selected: {category_name}"
                    item_selected = True
                else:
                    self.deselect_category()  # Use category deselect
            else:
                item_data["selected"] = False
            new_data.append(item_data)

        if not item_selected:
            self.deselect_category()  # Use category deselect

        self.category_recycle_view.data = new_data
        self.category_recycle_view.refresh_from_data()  # Refresh needed

        return True

    def deselect_category(self):
        """Helper to clear category selection state."""
        self.selected_category_data = None
        if self.status_label and not self.status_label.text.startswith("Error"):
            self.status_label.text = (
                "Manage your categories. Select one to edit/delete."
            )
        # Optional: Clear visual selection in data (handle_selection does this)
        # for item_data in self.category_recycle_view.data:
        #     item_data['selected'] = False
        # self.category_recycle_view.refresh_from_data()

    def get_selected_category(self):
        """Returns the data dict of the selected category or None."""
        return self.selected_category_data

    def open_add_category_popup(self):
        """Opens a popup to add a new category."""
        content = BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(10))
        popup_label = Label(text="Enter new category name:")  # Adapted text
        name_input = TextInput(
            multiline=False, hint_text="Category Name"
        )  # Adapted hint
        button_box = BoxLayout(size_hint_y=None, height=dp(50), spacing=dp(10))
        save_button = Button(text="Save")
        cancel_button = Button(text="Cancel")
        button_box.add_widget(save_button)
        button_box.add_widget(cancel_button)

        content.add_widget(popup_label)
        content.add_widget(name_input)
        content.add_widget(button_box)

        popup = Popup(
            title="Add Category", content=content, size_hint=(0.7, 0.4)
        )  # Adapted title

        def save_action(instance):
            category_name = name_input.text.strip()
            if category_name:
                self.add_category(category_name)  # Call category add method
                popup.dismiss()
            else:
                print("Category name cannot be empty.")
                self.status_label.text = "Category name cannot be empty."

        save_button.bind(on_press=save_action)
        cancel_button.bind(on_press=popup.dismiss)
        popup.open()

    def add_category(self, name):
        """Adds a new category to the database."""

        # Prevent adding "Uncategorized" manually if it should be default only
        if name.lower() == "uncategorized":
            self.status_label.text = "'Uncategorized' is a reserved name."
            print("Attempted to add reserved category name 'Uncategorized'.")
            return

        print(f"Attempting to add category: {name}")
        try:
            with SessionLocal() as db:
                # Use Category model
                exists = db.query(Category).filter(Category.name == name).first()
                if exists:
                    self.status_label.text = f"Category '{name}' already exists."
                    print(f"Category '{name}' already exists.")
                    return

                new_category = Category(name=name)  # Create Category object
                db.add(new_category)
                db.commit()
                print(f"Category '{name}' added successfully.")
                self.status_label.text = f"Category '{name}' added."
                self.load_categories_for_rv()  # Refresh category list

        except Exception as e:
            # db.rollback() # Handled by context manager
            error_msg = f"Error adding category '{name}': {e}"
            self.status_label.text = error_msg
            print(error_msg)

    def open_edit_category_popup(self):
        selected = self.get_selected_category()  # Use category getter
        if not selected:
            if self.status_label:
                self.status_label.text = "Select a category to edit."
            return

        category_id = selected["id"]
        category_name = selected["name"]

        # Prevent editing "Uncategorized"
        if category_name.lower() == "uncategorized":
            self.status_label.text = "Cannot edit the default 'Uncategorized' category."
            print("Attempted to edit reserved category 'Uncategorized'.")
            return

        print(
            f"Opening edit popup for Category ID: {category_id}, Name: {category_name}"
        )

        try:
            content = BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(10))
            popup_label = Label(
                text=f"Enter new name for '{category_name}':"
            )  # Adapted text
            name_input = TextInput(
                text=category_name, multiline=False, hint_text="New Category Name"
            )  # Adapted hint
            button_box = BoxLayout(size_hint_y=None, height=dp(50), spacing=dp(10))
            save_button = Button(text="Save Changes")
            cancel_button = Button(text="Cancel")
            button_box.add_widget(save_button)
            button_box.add_widget(cancel_button)
            content.add_widget(popup_label)
            content.add_widget(name_input)
            content.add_widget(button_box)
            popup = Popup(
                title="Edit Category", content=content, size_hint=(0.7, 0.4)
            )  # Adapted title

            def save_edit_action(instance):
                new_name = name_input.text.strip()
                if new_name and new_name != category_name:
                    # Prevent renaming TO "Uncategorized"
                    if new_name.lower() == "uncategorized":
                        if self.status_label:
                            self.status_label.text = (
                                "'Uncategorized' is a reserved name."
                            )
                        print("Attempted to rename category to 'Uncategorized'.")
                        # Keep popup open or dismiss? Dismiss is simpler.
                        # popup.dismiss() # Or just don't dismiss
                        return  # Stop processing
                    self.edit_category(
                        category_id, new_name
                    )  # Call category edit method
                    popup.dismiss()
                elif not new_name:
                    if self.status_label:
                        self.status_label.text = "Category name cannot be empty."
                else:
                    popup.dismiss()

            save_button.bind(on_press=save_edit_action)
            cancel_button.bind(on_press=popup.dismiss)
            popup.open()
        except Exception as e:
            print(f"Error opening Edit Category popup: {e}")
            if self.status_label:
                self.status_label.text = "Error opening edit dialog."

    def edit_category(self, category_id, new_name):
        if not new_name:
            self.status_label.text = "New category name cannot be empty."
            return
        # Redundant check, also done in popup save action, but good defense
        if new_name.lower() == "uncategorized":
            self.status_label.text = "'Uncategorized' is a reserved name."
            return

        print(f"Attempting to edit category ID {category_id} to '{new_name}'")
        try:
            with SessionLocal() as db:
                # Use Category model
                exists = (
                    db.query(Category)
                    .filter(Category.name == new_name, Category.id != category_id)
                    .first()
                )
                if exists:
                    self.status_label.text = (
                        f"Another category named '{new_name}' already exists."
                    )
                    print(f"Category '{new_name}' already exists.")
                    return

                category_to_edit = (
                    db.query(Category).filter(Category.id == category_id).first()
                )
                # Prevent editing "Uncategorized" again (defense in depth)
                if (
                    category_to_edit
                    and category_to_edit.name.lower() == "uncategorized"
                ):
                    self.status_label.text = (
                        "Cannot edit the default 'Uncategorized' category."
                    )
                    print(
                        "Attempted to edit reserved category 'Uncategorized' directly."
                    )
                    return

                if category_to_edit:
                    category_to_edit.name = new_name
                    db.commit()
                    print(f"Category ID {category_id} updated to '{new_name}'.")
                    self.status_label.text = f"Category '{new_name}' updated."
                    self.load_categories_for_rv()  # Refresh category list
                else:
                    self.status_label.text = (
                        f"Error: Category ID {category_id} not found for editing."
                    )
                    print(f"Category ID {category_id} not found.")

        except Exception as e:
            # db.rollback() # Handled by context manager
            error_msg = f"Error editing category ID {category_id}: {e}"
            self.status_label.text = error_msg
            print(error_msg)

    def confirm_delete_category(self):
        selected = self.get_selected_category()  # Use category getter
        if not selected:
            if self.status_label:
                self.status_label.text = "Select a category to delete."
            return

        category_id = selected["id"]
        category_name = selected["name"]

        # Prevent deleting "Uncategorized"
        if category_name.lower() == "uncategorized":
            self.status_label.text = (
                "Cannot delete the default 'Uncategorized' category."
            )
            print("Attempted to delete reserved category 'Uncategorized'.")
            return

        print(
            f"Opening delete confirmation for Category ID: {category_id}, Name: {category_name}"
        )

        dependency_text = self.check_category_dependencies(
            category_id
        )  # Call category dependency check

        try:
            content = BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(10))
            popup = None

            if dependency_text:
                warning_label = Label(
                    text=f"Cannot delete '{category_name}':\n{dependency_text}",
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
                confirm_label = Label(
                    text=f"Are you sure you want to delete category '{category_name}'?\nThis action cannot be undone.",
                    halign="center",
                )  # Adapted text
                button_box = BoxLayout(size_hint_y=None, height=dp(50), spacing=dp(10))
                delete_button = Button(text="Delete", background_color=(1, 0, 0, 1))
                cancel_button = Button(text="Cancel")
                button_box.add_widget(delete_button)
                button_box.add_widget(cancel_button)
                content.add_widget(confirm_label)
                content.add_widget(button_box)
                popup = Popup(
                    title="Confirm Deletion", content=content, size_hint=(0.7, 0.4)
                )  # Adapted title

                def delete_action(instance):
                    self.delete_category(category_id)  # Call category delete method
                    popup.dismiss()

                delete_button.bind(on_press=delete_action)
                cancel_button.bind(on_press=popup.dismiss)

            if popup:
                popup.open()
            else:
                raise Exception("Popup creation failed unexpectedly.")

        except Exception as e:
            print(f"Error opening Delete Confirmation popup: {e}")
            if self.status_label:
                self.status_label.text = "Error opening delete dialog."

    def check_category_dependencies(self, category_id):
        """Checks if a category has linked transactions. Returns warning text or None."""
        try:
            with SessionLocal() as db:
                # Check only Transactions linked to this category
                transaction_count = (
                    db.query(Transaction)
                    .filter(Transaction.category_id == category_id)
                    .count()
                )
                warnings = []
                if transaction_count > 0:
                    warnings.append(f"{transaction_count} linked transaction(s)")
                # No snapshot entries for categories
                return "\n".join(warnings) if warnings else None
        except Exception as e:
            print(f"Error checking dependencies for category {category_id}: {e}")
            return f"Error checking dependencies: {e}"

    def delete_category(self, category_id):
        # Dependency check is done in confirm_delete_category
        # Redundant check for "Uncategorized" (defense in depth)
        try:
            with SessionLocal() as db_check:
                cat_to_check = db_check.get(Category, category_id)
                if cat_to_check and cat_to_check.name.lower() == "uncategorized":
                    if self.status_label:
                        self.status_label.text = "Cannot delete 'Uncategorized'."
                    return
        except Exception:
            pass  # Ignore error here, main delete block will handle db issues

        print(f"Attempting to delete category ID {category_id}")
        try:
            with SessionLocal() as db:
                category_to_delete = (
                    db.query(Category).filter(Category.id == category_id).first()
                )
                if category_to_delete:
                    category_name = category_to_delete.name
                    db.delete(category_to_delete)
                    db.commit()
                    print(f"Category '{category_name}' (ID: {category_id}) deleted.")
                    if self.status_label:
                        self.status_label.text = f"Category '{category_name}' deleted."
                    self.load_categories_for_rv()  # Refresh category list
                    self.deselect_category()  # Clear selection
                else:
                    if self.status_label:
                        self.status_label.text = (
                            f"Error: Category ID {category_id} not found."
                        )
                    print(f"Category ID {category_id} not found for deletion.")

        except Exception as e:
            # db.rollback() # Handled by context manager
            error_msg = f"Error deleting category ID {category_id}: {e}"
            if self.status_label:
                self.status_label.text = error_msg
            print(error_msg)
