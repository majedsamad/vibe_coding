import os
import csv
import datetime
from kivy.uix.screenmanager import Screen
from kivy.properties import ObjectProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.filechooser import FileChooserListView
from kivy.uix.popup import Popup
from kivy.metrics import dp
from kivy.clock import Clock

from database import SessionLocal, Account, Transaction, Category


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
        self.update_transaction_display()  # Initial load attempt

    def show_import_dialog(self):
        content = BoxLayout(orientation="vertical", spacing=dp(5))
        filechooser = FileChooserListView(size_hint_y=0.8)
        content.add_widget(filechooser)

        button_box = BoxLayout(size_hint_y=0.1, height=dp(50), spacing=dp(5))
        load_button = Button(text="Load")
        cancel_button = Button(text="Cancel")
        button_box.add_widget(load_button)
        button_box.add_widget(cancel_button)
        content.add_widget(button_box)

        self.filechooser_popup = Popup(
            title="Import CSV File", content=content, size_hint=(0.9, 0.9)
        )

        load_button.bind(
            on_press=lambda x: self.import_csv(filechooser.path, filechooser.selection)
        )
        cancel_button.bind(on_press=self.filechooser_popup.dismiss)

        self.filechooser_popup.open()

    def import_csv(self, path, selection):
        if not selection:
            print("No file selected.")
            self.filechooser_popup.dismiss()
            return

        file_path = os.path.join(path, selection[0])
        print(f"Attempting to import CSV: {file_path}")

        imported_count = 0
        skipped_count = 0
        error_rows = []  # Store rows that caused errors

        try:
            with SessionLocal() as db:
                # --- Get default account and 'Uncategorized' category ---
                default_account = (
                    db.query(Account).filter(Account.name == "Cash").first()
                )
                if not default_account:
                    msg = "Error: Default 'Cash' account missing."
                    print(msg)
                    self.transaction_list_label.text = msg
                    self.filechooser_popup.dismiss()
                    return

                uncategorized_cat = (
                    db.query(Category).filter(Category.name == "Uncategorized").first()
                )
                if not uncategorized_cat:
                    msg = "Error: 'Uncategorized' category missing."
                    print(msg)
                    self.transaction_list_label.text = msg
                    self.filechooser_popup.dismiss()
                    return

                # --- Cache for Categories found/created during this import ---
                # Stores {'csv_category_name': category_db_object}
                category_cache = {"Uncategorized": uncategorized_cat}  # Pre-populate

                with open(file_path, mode="r", encoding="utf-8-sig") as infile:
                    reader = csv.reader(infile, delimiter=",")
                    try:
                        header = next(reader)  # Read header row
                    except StopIteration:
                        self.transaction_list_label.text = "Error: CSV file is empty."
                        self.filechooser_popup.dismiss()
                        return
                    print(f"CSV Header: {header}")

                    # --- Define column indices based on YOUR header ---
                    # Header: ['Transaction Date', 'Post Date', 'Description', 'Category', 'Type', 'Amount', 'Memo']
                    try:
                        # Use header.index() for robustness against column reordering
                        date_col_idx = header.index("Transaction Date")  # Was 0
                        desc_col_idx = header.index("Description")  # Was 2
                        cat_col_idx = header.index("Category")  # Was 3
                        amount_col_idx = header.index("Amount")  # Was 5
                        # type_col_idx = header.index('Type') # If needed later (index 4)
                    except ValueError as e:
                        msg = f"Error: Missing expected column in CSV header: {e}"
                        print(msg)
                        self.transaction_list_label.text = msg
                        self.filechooser_popup.dismiss()
                        return

                    # Minimum required columns check (optional but good)
                    min_cols = (
                        max(date_col_idx, desc_col_idx, cat_col_idx, amount_col_idx) + 1
                    )

                    for i, row in enumerate(reader, start=2):  # Start count from row 2
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
                            amount_str = (
                                row[amount_col_idx]
                                .strip()
                                .replace("$", "")
                                .replace(",", "")
                            )  # Clean amount

                            # --- Data Validation & Parsing ---
                            # Validate required fields are not empty
                            if not date_str or not description or not amount_str:
                                print(
                                    f"Skipping row {i}, missing required data (Date/Desc/Amount): {row}"
                                )
                                skipped_count += 1
                                error_rows.append((i, row, "Missing required data"))
                                continue

                            # Parse Date
                            # *** ADJUST THE FORMAT ('%m/%d/%Y') IF YOUR CSV USES A DIFFERENT ONE ***
                            # Examples: '%Y-%m-%d', '%m/%d/%y' (2-digit year), '%d-%b-%Y' (e.g., 26-Mar-2025)
                            try:
                                trans_date = datetime.datetime.strptime(
                                    date_str, "%m/%d/%Y"
                                ).date()
                            except ValueError:
                                print(
                                    f"Skipping row {i}, invalid date format: '{date_str}'. Expected MM/DD/YYYY. Row: {row}"
                                )
                                skipped_count += 1
                                error_rows.append(
                                    (i, row, f"Invalid date format: {date_str}")
                                )
                                continue

                            # Parse Amount
                            # *** ASSUMPTION: Amount column uses negative for expenses, positive for income ***
                            # If not, you might need to use the 'Type' column (index 4) to adjust the sign.
                            try:
                                trans_amount = float(amount_str)
                            except ValueError:
                                print(
                                    f"Skipping row {i}, invalid amount format: '{amount_str}'. Row: {row}"
                                )
                                skipped_count += 1
                                error_rows.append(
                                    (i, row, f"Invalid amount format: {amount_str}")
                                )
                                continue

                            # --- Get or Create Category ---
                            target_category = None
                            if not category_name_csv:  # Handle empty category field
                                target_category = uncategorized_cat
                            elif (
                                category_name_csv in category_cache
                            ):  # Check cache first
                                target_category = category_cache[category_name_csv]
                            else:
                                # Try finding category in DB
                                category_obj = (
                                    db.query(Category)
                                    .filter(Category.name == category_name_csv)
                                    .first()
                                )
                                if category_obj:
                                    target_category = category_obj
                                else:
                                    # Create new category if not found
                                    print(
                                        f"Creating new category: '{category_name_csv}' from row {i}"
                                    )
                                    new_cat = Category(name=category_name_csv)
                                    db.add(new_cat)
                                    # Flush to get the ID without full commit, allows rollback on later error
                                    db.flush()
                                    target_category = new_cat
                                # Add to cache whether found or created
                                category_cache[category_name_csv] = target_category

                            # Defensive check (should always have a category by now)
                            if not target_category:
                                print(
                                    f"Error: Failed to assign category for row {i}. Using Uncategorized. Row: {row}"
                                )
                                target_category = uncategorized_cat

                            # --- Create Transaction object ---
                            new_trans = Transaction(
                                date=trans_date,
                                description=description,
                                amount=trans_amount,
                                account_id=default_account.id,  # Still using default account
                                category_id=target_category.id,  # Use found/created category ID
                                # notes=row[memo_col_idx].strip() if len(row) > memo_col_idx else None # Optional: Add Memo
                            )
                            db.add(new_trans)
                            imported_count += 1

                        except Exception as e_row:
                            # Catch unexpected errors during row processing
                            print(
                                f"Skipping row {i} due to unexpected error: {e_row}. Row: {row}"
                            )
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
                self.update_transaction_display()  # Refresh display

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
        if not self.transaction_list_label:
            print("Cannot update transaction display: Label not ready.")
            return

        try:
            with SessionLocal() as db:
                recent_transactions = (
                    db.query(Transaction)
                    .order_by(Transaction.date.desc())
                    .limit(40)
                    .all()
                )  # Show more

                if not recent_transactions:
                    # Check if text indicates a recent import or error
                    current_text = self.transaction_list_label.text
                    if (
                        "Import complete" not in current_text
                        and "Error" not in current_text
                        and "No transactions found" not in current_text
                    ):
                        self.transaction_list_label.text = (
                            "No transactions found.\nImport a CSV file."
                        )
                    # else: keep the import status/error message
                    return

                # --- Format for display (Still placeholder - Needs RecycleView!) ---
                display_text = "Recent Transactions:\n"
                display_text += "{:<11} | {:<30} | {:>9} | {:<15} | {:<15}\n".format(
                    "Date", "Description", "Amount", "Category", "Account"
                )
                display_text += "-" * 80 + "\n"  # Separator

                for t in recent_transactions:
                    # Use db.get for potentially better performance than querying in loop
                    acc = db.get(Account, t.account_id)
                    cat = db.get(Category, t.category_id)
                    acc_name = acc.name if acc else "N/A"
                    cat_name = (
                        cat.name if cat else "Uncategorized"
                    )  # Default if category missing

                    display_text += (
                        "{:<11} | {:<30} | {:>9.2f} | {:<15} | {:<15}\n".format(
                            str(t.date),
                            (t.description[:28] + "..")
                            if len(t.description) > 30
                            else t.description,
                            t.amount,
                            (cat_name[:13] + "..") if len(cat_name) > 15 else cat_name,
                            (acc_name[:13] + "..") if len(acc_name) > 15 else acc_name,
                        )
                    )

                self.transaction_list_label.text = display_text

        except Exception as e:
            print(f"Error loading transactions from DB: {e}")
            self.transaction_list_label.text = f"Error loading transactions: {e}"
