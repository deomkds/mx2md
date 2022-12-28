#  Copyright (c) 2022, Marcus Vinícius Rodrigues Cunha
#  SPDX-License-Identifier: BSD-2-Clause

import json
import os
import sys
import time
import re
from zipfile import ZipFile


class Note:
    def __init__(self, memorix_entry, categories):
        self._entry = memorix_entry
        self._categories = categories

        self.title = self.determine_title()
        self.id = self.determine_id()
        self.flag = self.determine_flag()
        self.font_size = self.determine_font_size()
        self.ctime = self.determine_ctime()
        self.mtime = self.determine_mtime()
        self.category = self.determine_category()
        self.attachments = self.determine_attachments()
        self.content = self.determine_content()
        self.save_dir = self.determine_save_dir()
        self.file_name = self.determine_file_name()

    def determine_title(self):
        if ("title" in self._entry) and (self._entry["title"].strip() != ""):
            return self._entry["title"].strip()
        else:
            return "Note " + str(self._entry["order"])

    def determine_id(self):
        return self._entry["sections"][0]["id"]

    def determine_flag(self):
        return self._entry["flags"]

    def is_trashed(self):
        return test_bit(self.flag, 1)

    def is_archived(self):
        return test_bit(self.flag, 12)

    def is_pinned(self):
        return test_bit(self.flag, 10)

    def is_list(self):
        return test_bit(self.flag, 2)

    def checked_to_bottom(self):
        return test_bit(self.flag, 4)

    def determine_font_size(self):
        bit_5 = test_bit(self.flag, 5)
        bit_6 = test_bit(self.flag, 6)
        bit_7 = test_bit(self.flag, 7)  # Exclusive. If this is True, the others will always be False.

        if bit_7:
            return "Tiny"
        elif bit_5 and not bit_6:
            return "Large"
        elif not bit_5 and bit_6:
            return "Huge"
        elif bit_5 and bit_6:
            return "Small"
        else:
            return "Normal"

    def determine_ctime(self):
        return float(self._entry["createdMillis"]) / 1000

    def determine_mtime(self):
        return float(self._entry["lastModifiedMillis"]) / 1000

    def determine_category(self):
        for item in self._categories:
            if item["num"] == self._entry["colorNum"]:
                return item["title"]

    def determine_content(self):
        if self.attachments:
            attachments = f"\n\nAttachments ({len(self.attachments)}):"
            for item in self.attachments:
                attachments += f"\n![[{item}]]\n"
        else:
            attachments = ""

        if self._entry["sections"][0]["checkable"] is False:
            # For normal notes, that have a single section.
            return self._entry["sections"][0]["text"] + attachments
        else:
            # For list notes, that have multiple sections (each line is a section).
            text_content = ""
            for list_item in self._entry["sections"]:
                if list_item["checked"]:
                    text_content += f'- [x] {list_item["text"]}\n'
                else:
                    text_content += f'- [ ] {list_item["text"]}\n'
            return text_content + attachments

    def determine_attachments(self):
        return self._entry["attachments"]

    def determine_save_dir(self):
        if self.is_trashed() and separate_trash and not ignore_trash:
            path = os.path.join(dest_path, "Trash")
        elif self.is_archived() and separate_archive and not ignore_archive:
            path = os.path.join(dest_path, "Archive")
        else:
            path = dest_path

        return os.path.join(path, self.category)

    def determine_file_name(self):
        prefix = epoch_to_readable(self.ctime, "%Y-%m-%d")
        # Removes special characters to make filenames for Windows/OneDrive.
        middle = re.sub(r'[^\w_. -]', '', self.title).strip()
        if middle == "":
            middle = "Note " + str(self._entry["order"])

        return f"{prefix} {middle[:50]}"

    def write_to_disk(self, path):
        with open(path, "w") as destination:
            destination.write(self.content)
        set_original_timestamp(path, self.mtime, self.ctime)


class MemorixDB:
    def __init__(self, path):
        self._backup_file = path

        self.data = self.extract_data()
        self.notes = self.data["entries"]
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

    def write_attachment(self, attachment_name, path):
        with ZipFile(self._backup_file, "r") as zip_file:
            for file_name in zip_file.namelist():
                if file_name == attachment_name:
                    if not os.path.exists(os.path.join(path, attachment_name)):
                        zip_file.extract(attachment_name, path=path)


class SyncDB:
    def __init__(self, path):
        self.path = os.path.join(path, "sync_db.json")
        self.data = self.read()
        self.notes = self.data["notes"]
        self.attachments = self.data["attachments"]

    def add_note(self, note_id, path, mtime):
        self.notes.append({"id": note_id, "path": path, "mtime": mtime})

    def read(self):
        if os.path.exists(self.path):
            with open(self.path, "r") as json_db:
                return json.load(json_db)
        else:
            return {"notes": [], "attachments": []}

    def write(self):
        parsed_data = json.dumps(self.data)
        with open(self.path, "w") as json_db:
            json_db.write(parsed_data)


def test_bit(int_type, offset):
    # https://wiki.python.org/moin/BitManipulation
    # testBit() returns a nonzero result, 2**offset, if the bit at 'offset' is one.
    # Slightly modified by me to return a boolean value.

    mask = 1 << offset
    if (int_type & mask) != 0:
        return True
    else:
        return False


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


def print_help():
    print("Usage: python3 mx2md.py [OPTION]...\n")
    print("Convert a Memorix Backup file (*.mxbk) into a folder of Markdown files.")
    print("Supports incremental syncs using a database to track file changes.\n")
    print("Required arguments:")
    print("  -i        Specifies an input file or a folder containing Memorix Backup files (*.mxbk).")
    print("            When a folder is specified, the most recent '*.mxbk' file will be used.\n")
    print("  -o        Specifies the destination folder.\n")
    print("Optional arguments:")
    print("  --safe-mode                 Enables Safe Mode where no files are deleted from disk.")
    print("  --verbose                   Enables verbose output with debug information.")
    print("  --help                      Prints this help.")
    print("  --ignore-trash              Don't extract notes from the trash.")
    print("  --ignore-archive            Don't extract archived notes.")
    print("  --ignore-attachments        Don't extract note attachments.")
    print("  --separate-trash            Place notes from the trash in a separate 'Trash' folder.")
    print("  --separate-archive          Place archived notes in a separate 'Archive' folder.")
    print("  --separate-attachments      Place note attachments in a separate 'Attachments' folder.")


def try_mkdir(path):
    if not os.path.exists(path):
        try:
            os.mkdir(path)
        except OSError as error:
            print(f"Error: {error}")
            sys.exit()


# Main application routine. =========================================================
memorix_db_path = ""
memorix_db_file = ""
dest_path = ""

if len(sys.argv) < 5 or ("--help" in sys.argv):
    print_help()
    sys.exit()

if ("-i" in sys.argv) and ("-o" in sys.argv):
    memorix_db_path = sys.argv[sys.argv.index("-i") + 1]
    dest_path = os.path.join(sys.argv[sys.argv.index("-o") + 1], "Memorix")
else:
    print("ERROR: Input and output must be specified.\n")
    print_help()
    sys.exit()

safe_mode = "--safe-mode" in sys.argv
debug_mode = "--verbose" in sys.argv

ignore_trash = "--ignore-trash" in sys.argv
ignore_archive = "--ignore-archive" in sys.argv
ignore_attachments = "--ignore-attachments" in sys.argv

separate_trash = "--separate-trash" in sys.argv
separate_archive = "--separate-archive" in sys.argv
separate_attachments = "--separate-attachments" in sys.argv

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
try_mkdir(dest_path)

mxdb = MemorixDB(memorix_db_file)
sync_db = SyncDB(dest_path)
every_filename = []

for i, j in enumerate(mxdb.notes, start=1):

    dbgln(f"\nNote {i}: processing note {i} out of {mxdb.notes_count}.")
    note = Note(j, mxdb.categories)

    if note.is_trashed() and separate_trash:
        dbgln(f"Note {i}: note is in the Trash.")
        try_mkdir(os.path.dirname(note.save_dir))
    elif note.is_archived() and separate_archive:
        dbgln(f"Note {i}: note is Archived.")
        try_mkdir(os.path.dirname(note.save_dir))

    dbgln(f"Note {i}: note will be saved in '{note.category}' subfolder.")
    try_mkdir(note.save_dir)

    dbgln(f"Note {i}: filename will be '{note.file_name}.md'.")
    full_path = os.path.join(note.save_dir, f"{note.file_name}.md")

    name_counter = 1
    while True:
        # To avoid files with same name in a directory.
        if full_path.lower() in every_filename:
            full_path = os.path.join(note.save_dir, f"{note.file_name} {name_counter}.md")
            dbgln(f"Note {i}: filename already exists, will try '{note.file_name} {name_counter}.md'.")
            name_counter += 1
        else:
            every_filename.append(full_path.lower())
            break

    in_db = False

    # FIXME: add version number to the database
    #        to recreate entire folder structure
    #        after script updates

    for entry in sync_db.notes:
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

    if note.attachments and not ignore_attachments:
        dbgln(f"Note {i}: note has {len(note.attachments)} attachments.")
        if separate_attachments:
            attachment_dir = os.path.join(dest_path, "Attachments")
            try_mkdir(attachment_dir)
        else:
            attachment_dir = note.save_dir
        dbgln(f"Note {i}: attachments will be saved in '{os.path.basename(attachment_dir)}' directory.")

        for attached_file in note.attachments:
            mxdb.write_attachment(attached_file, attachment_dir)


sync_db.write()
dbgln("\nDatabase written to disk.")

dbgln(f"\nChecking for deletions.")
file_deletions = 0
folder_deletions = 0
files_in_dest = list_files_recursively(dest_path, ".md")

for md_file_path in files_in_dest:
    file_in_db = False
    for entry in sync_db.notes:
        if entry["path"] == md_file_path:
            file_in_db = True
            break
    if not file_in_db and not safe_mode:
        dbgln(f"File {md_file_path} is not in database and will be deleted.")
        os.remove(md_file_path)
        file_deletions += 1
        if not os.listdir(os.path.dirname(md_file_path)):
            os.rmdir(os.path.dirname(md_file_path))
            folder_deletions += 1

dbgln(f"File(s) deleted: {file_deletions} file(s).\nFolder(s) deleted: {folder_deletions} folder(s).")
