#  Copyright (c) 2022, Marcus Vinícius Rodrigues Cunha
#  SPDX-License-Identifier: BSD-2-Clause

import json
import os
import sys
import time
import re
from zipfile import ZipFile


def dbgln(*args):
    if debug_mode:
        print(*args)


def list_files(path, extension):
    files = os.scandir(path)
    filtered = []
    for file in files:
        if file.name.endswith(extension):
            filtered.append(file)
    return filtered


def list_files_recursively(path, extension):
    files = os.walk(path, topdown=True)
    filtered = []
    for (root, dirs, files) in files:
        for items in files:
            file_path = os.path.join(root, items)
            if file_path.endswith(extension):
                filtered.append(file_path)
    return filtered


def epoch_to_readable(timestamp, date_format):
    timestamp_string = time.ctime(timestamp)       # As a timestamp string.
    time_object = time.strptime(timestamp_string)  # To a timestamp object.
    return time.strftime(date_format, time_object)      # To my format.


def set_original_timestamp(path, mtime, ctime):
    os.utime(path, (mtime, ctime))


class Note:
    def __init__(self, memorix_entry, categories):
        self._entry = memorix_entry
        self._categories = categories

        self.title = self.determine_title()
        self.id = self.determine_id()
        self.ctime = self.determine_ctime()
        self.mtime = self.determine_mtime()
        self.category = self.determine_category()
        self.content = self.determine_content()
        self.file_name = self.determine_file_name()

    def determine_title(self):
        if ("title" in self._entry) and (self._entry["title"].strip() != ""):
            return self._entry["title"].strip()
        else:
            return "Note " + str(self._entry["order"])

    def determine_id(self):
        return self._entry["sections"][0]["id"]

    def determine_ctime(self):
        return float(self._entry["createdMillis"]) / 1000

    def determine_mtime(self):
        return float(self._entry["lastModifiedMillis"]) / 1000

    def determine_category(self):
        for item in self._categories:
            if item["num"] == self._entry["colorNum"]:
                return item["title"]

    def determine_content(self):
        if self._entry["sections"][0]["checkable"] is False:
            # For normal notes, that have a single section.
            return self._entry["sections"][0]["text"]
        else:
            # For list notes, that have multiple sections (each line is a section).
            text_content = ""
            for list_item in self._entry["sections"]:
                if list_item["checked"]:
                    text_content += f'- [x] {list_item["text"]}\n'
                else:
                    text_content += f'- [ ] {list_item["text"]}\n'
            return text_content

    def determine_file_name(self):
        prefix = epoch_to_readable(self.ctime, "%Y-%m-%d")
        # Removes special characters in order to make safe filenames for Windows/OneDrive.
        middle = re.sub(r'[^\w_. -]', '', self.title).strip()
        if middle == "":
            middle = "Note " + str(self._entry["order"])

        return f"{prefix} {middle[:50]}"

    def write_to_disk(self, path):
        with open(path, "w") as destination:
            destination.write(self.content)
        set_original_timestamp(path, self.mtime, self.ctime)


def find_latest_backup(path):
    extension = ".mxbk"
    backups = list_files(path, extension)

    if not backups:
        return None

    most_recent_time = 0.0
    most_recent_indx = 0

    for index, backup in enumerate(backups):
        creation_time = os.path.getctime(backup.path)
        if creation_time > most_recent_time:
            most_recent_time = creation_time
            most_recent_indx = index

    return backups[most_recent_indx].path


class MemorixDB:
    def __init__(self, path):
        self._backup_file = path

        self.data = self.extract_data()
        self.notes_list = self.data["entries"]
        self.notes_count = len(self.data["entries"])
        self.categories = self.extract_categories()

    def extract_data(self):
        with ZipFile(self._backup_file, "r") as zip_file:
            for file_name in zip_file.namelist():
                if file_name.endswith(".json"):
                    json_file = file_name
                    break

            with zip_file.open(json_file, "r") as notes_file:
                return json.load(notes_file)

    def extract_categories(self):
        return json.loads(self.data["prefs"]["pref_categories"])


class SyncDB:
    def __init__(self, path):
        self.path = os.path.join(path, "sync_db.json")
        self.data = self.read()
        self.entries = self.data["entries"]

    def add_note(self, note_id, path, mtime):
        self.entries.append({"id": note_id, "path": path, "mtime": mtime})

    def read(self):
        if os.path.exists(self.path):
            with open(self.path, "r") as json_db:
                return json.load(json_db)
        else:
            return {"entries": []}

    def write(self):
        parsed_data = json.dumps(self.data)
        with open(self.path, "w") as json_db:
            json_db.write(parsed_data)


def print_help():
    print("Usage: python3 mx2md.py [OPTION]...")
    print("Convert a Memorix Backup file (*.mxbk) into a folder of Markdown files.")
    print("Supports subsequent incremental syncs using a database and tracking file changes.\n")
    print("  -i        Specifies an input file or a folder containing Memorix Backup files (*.mxbk).")
    print("            When a folder is specified, the most recent '*.mxbk' file will be used.\n")
    print("  -o        Specifies the destination folder.")
    print("  -v        Verbose output.")
    print("  -h        Prints this help.")


# Main application routine. =========================================================
memorix_db_path = ""
memorix_db_file = ""
dest_path = ""

if len(sys.argv) < 5 or ("-h" in sys.argv):
    print_help()
    sys.exit()

if ("-i" in sys.argv) and ("-o" in sys.argv):
    memorix_db_path = sys.argv[sys.argv.index("-i") + 1]
    dest_path = os.path.join(sys.argv[sys.argv.index("-o") + 1], "Memorix")
else:
    print("ERROR: Both input and output must be specified.\n")
    print_help()
    sys.exit()

if "-v" in sys.argv:
    debug_mode = True
else:
    debug_mode = False

if os.path.exists(memorix_db_path):
    if memorix_db_path.endswith(".mxbk"):
        memorix_db_file = memorix_db_path
    else:
        memorix_db_file = find_latest_backup(memorix_db_path)

    if memorix_db_file is None:
        print(f"Memorix Database file not found in folder '{memorix_db_path}'.")
        sys.exit()
else:
    print("Memorix Database file or folder not found.")
    sys.exit()

dbgln(f"Data will be exported to folder '{dest_path}'.")

try:
    os.mkdir(dest_path)
except FileExistsError:
    pass
except OSError as error:
    print(f"Error: {error}")
    sys.exit()

mxdb = MemorixDB(memorix_db_file)
sync_db = SyncDB(dest_path)
every_filename = []

for i, j in enumerate(mxdb.notes_list, start=1):

    dbgln(f"\nNote {i}: processing note {i} out of {mxdb.notes_count}.")
    note = Note(j, mxdb.categories)

    save_dir = os.path.join(dest_path, note.category)

    dbgln(f"Note {i}: note will be saved in '{note.category}' subfolder.")
    if not os.path.exists(save_dir):
        dbgln(f"Note {i}: subfolder for '{note.category}' does not exist and will be created.")
        os.mkdir(save_dir)

    name_counter = 1
    full_path = os.path.join(save_dir, f"{note.file_name}.md")
    dbgln(f"Note {i}: filename will be '{note.file_name}.md'.")

    while True:
        # To avoid having two files with the same name in the same directory.
        if full_path.lower() in every_filename:
            full_path = os.path.join(save_dir, f"{note.file_name} {name_counter}.md")
            dbgln(f"Note {i}: filename already exists, will try '{note.file_name} {name_counter}.md'.")
            name_counter += 1
        else:
            every_filename.append(full_path.lower())
            break

    in_db = False

    for entry in sync_db.entries:
        if entry["id"] == note.id:
            dbgln(f"Note {i}: note found in database.")
            in_db = True
            if entry["mtime"] < note.mtime or not os.path.exists(full_path):
                dbgln(f"Note {i}: file is outdated and will be updated.")
                note.write_to_disk(full_path)
                entry["mtime"] = note.mtime
            else:
                dbgln(f"Note {i}: file is most recent and will be ignored.")
            break

    if not in_db:
        dbgln(f"Note {i}: note not found in database and will be added.")
        note.write_to_disk(full_path)
        sync_db.add_note(note.id, full_path, note.mtime)

sync_db.write()
dbgln("\nDatabase written to disk.")

dbgln(f"\nChecking for deletions.")
deletions = 0
files_in_dest = list_files_recursively(dest_path, ".md")

for md_file_path in files_in_dest:
    file_in_db = False
    for entry in sync_db.entries:
        if entry["path"] == md_file_path:
            file_in_db = True
            break
    if not file_in_db:
        dbgln(f"File {md_file_path} is not in database and will be deleted.")
        os.remove(md_file_path)
        deletions += 1

dbgln(f"{deletions} file(s) deleted.")
