from kivy.app import App
from kivy.uix.screenmanager import ScreenManager

from database import init_db

from account_management_screen import AccountManagementScreen
from category_management_screen import CategoryManagementScreen
from account_screen import AccountsScreen
from budget_screen import BudgetScreen


# --- Screen Manager ---
class MyScreenManager(ScreenManager):
    pass


# --- Main App Class ---
class BudgetApp(App):
    def build(self):
        init_db()  # Create database tables if they don't exist
        sm = MyScreenManager()
        return sm


# --- Run the App ---
if __name__ == "__main__":
    BudgetApp().run()
