#  Copyright (c) 2022, Marcus Vinícius Rodrigues Cunha
#  SPDX-License-Identifier: BSD-2-Clause

import json
import os
import sys
import time
import re
import hashlib
from zipfile import ZipFile
from datetime import datetime


class Note:
    def __init__(self, memorix_entry, categories):
        self._entry = memorix_entry
        self._categories = categories

        self.hash = self.generate_hash()
        self.title = self.determine_title()
        self.id = self.determine_id()
        self.flag = self.determine_flag()
        self.order = self.determine_order()
        self.font_size = self.determine_font_size()
        self.ctime = self.determine_ctime()
        self.mtime = self.determine_mtime()
        self.category = self.determine_category()
        self.attachments = self.determine_attachments()
        self.content = self.determine_content()
        self.save_dir = self.determine_save_dir()
        self.file_name = self.determine_file_name()

    def generate_hash(self):
        byte_string = f"{self._entry}".encode("utf-8")
        return hashlib.md5(byte_string).hexdigest()

    def determine_title(self):
        if ("title" in self._entry) and (self._entry["title"].strip() != ""):
            return self._entry["title"].strip()
        else:
            return f"Note {self._entry["order"]}"

    def determine_id(self):
        return self._entry["sections"][0]["id"]

    def determine_flag(self):
        return self._entry["flags"]

    def determine_order(self):
        return self._entry["order"]

    def is_empty(self):
        return True if self.content == "" else False

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
            middle = f"Note {self.order}"

        return f"{prefix} {middle[:50]}".strip()

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

    def remove_note(self, note_id):
        for position, single_note in enumerate(self.notes):
            if single_note["id"] == note_id:
                self.notes.pop(position)

    def pop_note(self, note_pos):
        self.notes.pop(note_pos)

    def get_note_hash_from_pos(self, note_pos: int):
        return self.notes[note_pos]["id"]

    def get_note_path_from_pos(self, note_pos: int):
        return self.notes[note_pos]["path"]

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


def log(text, essential=False, line_break=False):
    if debug_mode or essential:
        moment_obj = datetime.now()
        moment = moment_obj.strftime("%Y-%m-%d %H:%M:%S")
        path = os.path.join(dest_path, 'export_log.md')
        br = f"\n" if line_break else f""
        note_number = f"Note {current_file} -> " if current_file else f""
        output_line = f"{br}{moment}: {note_number}{text}"
        debug_print(output_line)
        with open(path, "a") as log_file:
            log_file.write(f"{output_line}\n")


def debug_print(*args):
    if debug_mode:
        print(*args)


def test_bit(int_type, offset):
    # https://wiki.python.org/moin/BitManipulation
    # testBit() returns a nonzero result, 2**offset, if the bit at 'offset' is one.
    # Slightly modified by me to return a boolean value.

    mask = 1 << offset
    if (int_type & mask) != 0:
        return True
    else:
        return False


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
    print("Usage: python3 mx2md.py [OPTIONS]...\n")
    print("Convert a Memorix Backup file (*.mxbk) to a folder of Markdown files.")
    print("Supports incremental syncs, tracking changes with a database.\n")
    print("Required arguments:")
    print("  -i        Specifies input backup file (*.mxbk) or folder.")
    print("            When specifying a folder, the most recent backup file will be used.\n")
    print("  -o        Specifies the destination folder.\n")
    print("Optional arguments:")
    print("  --safe-mode                 Enables Safe Mode where no files are deleted from disk.")
    print("  --verbose                   Enables verbose output and logging for debugging.")
    print("  --help                      Prints this help message.")
    print("  --skip-trash                Skip notes from the trash.")
    print("  --skip-archive              Skip archived notes.")
    print("  --skip-empty                Skip notes without content.")
    print("  --ignore-attachments        Don't extract note attachments.")
    print("  --separate-trash            Place notes from the trash in a separate 'Trash' folder.")
    print("  --separate-archive          Place archived notes in a separate 'Archive' folder.")
    print("  --separate-attachments      Place attachments in a separate 'Attachments' folder.")


def try_mkdir(path):
    if not os.path.exists(path):
        try:
            os.mkdir(path)
        except OSError as error:
            print(f"Error: {error}")
            sys.exit()


# Main application routine. =========================================================
if __name__ == "__main__":
    # Declare "empty" variables to use later.
    mxdb_folder = ""
    mxdb_file = ""
    dest_path = ""
    current_file = 0

    # Setup some counters for summary.
    unchanged_notes = 0
    new_notes = 0
    updated_notes = 0
    skipped_empty_notes = 0
    skipped_trashed_notes = 0
    skipped_archived_notes = 0

    # Check command line parameters.
    if len(sys.argv) < 5 or ("--help" in sys.argv):
        print_help()
        sys.exit()

    if ("-i" in sys.argv) and ("-o" in sys.argv):
        mxdb_folder = sys.argv[sys.argv.index("-i") + 1]
        dest_path = os.path.join(sys.argv[sys.argv.index("-o") + 1], "Memorix")
    else:
        print("ERROR: Input and output must be specified.\n")
        print_help()
        sys.exit()

    if os.path.exists(mxdb_folder):
        if mxdb_folder.endswith(".mxbk"):
            mxdb_file = mxdb_folder
        else:
            mxdb_file = find_latest_backup(mxdb_folder)

        if mxdb_file is None:
            print(f"Memorix Database file not found in folder '{mxdb_folder}'.")
            sys.exit()
    else:
        print("Memorix Database file or folder not found.")
        sys.exit()

    # Set working variables.
    safe_mode = "--safe-mode" in sys.argv
    debug_mode = "--verbose" in sys.argv

    ignore_trash = "--ignore-trash" in sys.argv
    ignore_archive = "--ignore-archive" in sys.argv
    ignore_attachments = "--ignore-attachments" in sys.argv
    ignore_empty_notes = "--ignore-empty-notes" in sys.argv

    separate_trash = "--separate-trash" in sys.argv
    separate_archive = "--separate-archive" in sys.argv
    separate_attachments = "--separate-attachments" in sys.argv

    # Try to create destination folder.
    try_mkdir(dest_path)
    log(f"Data will be exported to folder '{dest_path}'.")

    # Open Memorix backup file.
    mxdb = MemorixDB(mxdb_file)

    # Create an empty list and store every note on it.
    current_notes = []
    for raw_note in mxdb.notes:
        note = Note(raw_note, mxdb.categories)
        current_notes.append(note)

    # Removes empty notes from the processing list.
    notes_to_ignore = []
    for pos, note in enumerate(current_notes):
        if note.is_empty() and ignore_empty_notes:
            notes_to_ignore.append(pos)
            skipped_empty_notes += 1
        elif note.is_trashed() and ignore_trash:
            notes_to_ignore.append(pos)
            skipped_trashed_notes += 1
        elif note.is_archived() and ignore_archive:
            notes_to_ignore.append(pos)
            skipped_archived_notes += 1

    notes_to_ignore.sort(reverse=True)

    for index in notes_to_ignore:
        current_notes.pop(index)

    # Open or create my database.
    sync_db = SyncDB(dest_path)

    # Collect every filepath to avoid collisions.
    filepaths = []

    for pos, note in enumerate(current_notes, start=1):

        # So log() knows which file we are working on right now.
        current_file = pos

        log(f"Processing note {pos} out of {len(current_notes)}.", line_break=True)

        # Try to create folders based on the options selected by the user.
        if note.is_trashed() and separate_trash:
            log(f"Note is in the Trash.")
            try_mkdir(os.path.dirname(note.save_dir))  # Am I removing the category sub folder here?
        elif note.is_archived() and separate_archive:
            log(f"Note is Archived.")
            try_mkdir(os.path.dirname(note.save_dir))  # Am I removing the category sub folder here?

        log(f"Saving note in subfolder '{note.category}'.")
        try_mkdir(note.save_dir)

        # Generate full path with file name and extension for current note.
        log(f"Using '{note.file_name}.md' as filename.")
        full_path = os.path.join(note.save_dir, f"{note.file_name}.md")

        # This basically tests if the full path already exists
        # and if it does, generates a new name to avoid collisions.
        name_counter = 1
        while True:
            if full_path.lower() in filepaths:
                full_path = os.path.join(note.save_dir, f"{note.file_name} {name_counter}.md")
                log(f"Filename already in use, trying '{note.file_name} {name_counter}.md'.")
                name_counter += 1
            else:
                filepaths.append(full_path.lower())
                break

        # Then, before writing files to disk, first
        # check if it has an entry in the database.

        in_db = False

        # Go over every entry in the database looking for our current hash.
        for entry in sync_db.notes:
            if entry["id"] == note.hash:
                log(f"Note with hash '{note.hash}' already in database.")
                in_db = True
                # If the note is found in the database, check its
                # modified time to determine if it needs to be updated.
                if entry["mtime"] < note.mtime or not os.path.exists(full_path):
                    updated_notes += 1
                    log(f"Updating file.")
                    note.write_to_disk(full_path)  # If true, update the file.
                    entry["mtime"] = note.mtime    # Then update the entry in the database.
                else:
                    unchanged_notes += 1
                    log(f"File is most recent.")   # If false, just ignore it, writing nothing to disk.
                break

        # If the hash isn't found in the database, add it.
        if not in_db:
            new_notes += 1
            log(f"Adding new note with hash '{note.hash}' to the database.")
            note.write_to_disk(full_path)                       # Write note to disk.
            sync_db.add_note(note.hash, full_path, note.mtime)  # Then update the database.

        # Process attachments. This has its flaws, but I'm ignoring it for now.
        if note.attachments and not ignore_attachments:
            log(f"Note has {len(note.attachments)} attachments.")
            if separate_attachments:
                attachment_dir = os.path.join(dest_path, "Attachments")
                try_mkdir(attachment_dir)
            else:
                attachment_dir = note.save_dir
            log(f"Saving attachments in '{os.path.basename(attachment_dir)}' directory.")

            for attached_file in note.attachments:
                mxdb.write_attachment(attached_file, attachment_dir)

    current_file = 0  # So log() knows we're not in the main notes loop anymore.

    # Out of the notes loop, we look for files that can be deleted.

    # List every file at the destination.
    destination_folder = list_files_recursively(dest_path, ".md")

    # Set up some counters to be used later.
    log(f"Checking for file deletions.", line_break=True)
    file_deletions = 0
    folder_deletions = 0

    # Check every filepath
    for md_file in destination_folder:
        file_in_db = False  # Assume the file is not in the database.
        for path in filepaths:
            if md_file.lower() == path:
                file_in_db = True  # If the path is found in the database, mark it for keeping.
                break
        # Delete stuff that hasn't been found in the database.
        if not file_in_db and not safe_mode:
            log(f"Deleting file at '{md_file}'.")
            os.remove(md_file)
            file_deletions += 1
            # Remove empty folders.
            if not os.listdir(os.path.dirname(md_file)):
                os.rmdir(os.path.dirname(md_file))
                folder_deletions += 1



    # Setup some more counters.
    log("Performing database cleanup.", line_break=True)
    entry_deletions = 0

    # Perform database cleanup.
    invalid_indexes = []
    for pos, entry in enumerate(sync_db.notes):
        invalid_entry = True  # Assume the entry is invalid.
        # Loop over every hash of the current session.
        for note in current_notes:
            if entry["id"] == note.hash:
                invalid_entry = False
                break
        if invalid_entry:
            # If the entry is invalid, take note of its position.
            invalid_indexes.append(pos)

    # Because we use indexes to delete stuff from the database, start deleting from the end.
    # This avoids messing up the position of items.
    invalid_indexes.sort(reverse=True)

    for index in invalid_indexes:
        note_path = sync_db.get_note_path_from_pos(index)
        log(f"Deleting note with path '{note_path}' from the database.")
        sync_db.pop_note(index)
        entry_deletions += 1

    log("Writing database to disk.", line_break=True)
    sync_db.write()

    # Presents a summary because it's cool.
    log(f"Added {new_notes} new note(s) to the database.", line_break=True, essential=True)
    log(f"Updated {updated_notes} existing note(s).", essential=True)
    log(f"Kept {unchanged_notes} note(s) unchanged.", essential=True)

    total_notes = new_notes + updated_notes + unchanged_notes

    if ignore_empty_notes:
        log(f"Ignored {skipped_empty_notes} empty note(s)", essential=True)
        total_notes += skipped_empty_notes

    if ignore_trash:
        log(f"Ignored {skipped_trashed_notes} trashed note(s)", essential=True)
        total_notes += skipped_trashed_notes

    if ignore_archive:
        log(f"Ignored {skipped_archived_notes} archived note(s)", essential=True)
        total_notes += skipped_archived_notes

    log(f"Expected to process {mxdb.notes_count} note(s).", essential=True)
    log(f"Processed a total of {total_notes} note(s).", essential=True)

    percentage = (total_notes / mxdb.notes_count) * 100

    log(f"Notes processed: {percentage:.2f}%", essential=True)

    log(f"Deleted {file_deletions} file(s) and {folder_deletions} folder(s).", essential=True)
    log(f"Deleted {entry_deletions} entry(ies) from the database.", essential=True)
