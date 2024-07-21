# mx2md
Extract notes from Memorix Backup files (*.mxbk).

[Memorix](https://play.google.com/store/apps/details?id=panama.android.notes) is a note-taking application for Android devices.

This script extracts notes from a Memorix backup and saves them as Markdown files.
- Notes are organized into subfolders based on their assigned categories.
- Synced notes are tracked using a database, enabling incremental syncs.
- You can use folders as input: the script will select the most recent backup file from within the folder.

# Usage
```
python3 mx2md.py -i [input file or folder] -o [output folder] [options]
```
| Option                 | Description                                                                                                                                             |
|:-----------------------|:--------------------------------------------------------------------------------------------------------------------------------------------------------|
| -i                     | Specifies an input file or a folder containing Memorix Backup files (\*.mxbk). When a folder is specified, the most recent '\*.mxbk' file will be used. |
| -o                     | Specifies the destination folder. A subfolder called Memorix will be created at the specified path.                                                     |
| --safe-mode            | Enables Safe Mode where no files are deleted from disk.                                                                                                 |
| --verbose              | Enables verbose output with debug information.                                                                                                          |
| --help                 | Prints this help.                                                                                                                                       |
| --ignore-trash         | Don't extract notes from the trash.                                                                                                                     |
| --ignore-archive       | Don't extract archived notes.                                                                                                                           |
| --ignore-attachments   | Don't extract note attachments.                                                                                                                         |
| --separate-trash       | Place notes from the trash in a separate 'Trash' folder.                                                                                                |
| --separate-archive     | Place archived notes in a separate 'Archive' folder.                                                                                                    |
| --separate-attachments | Place note attachments in a separate 'Attachments' folder.                                                                                              |

# Example
This script allows you to maintain a copy of your Memorix notes as Markdown files. Here’s one way to use it:
1. Setup Memorix to make periodic backups.
2. Sync those backups to a PC using a cloud provider like OneDrive or Google Drive.
3. Pass the folder containing the backups as input to `mx2md`.
4. Run `mx2md` periodically to output the Markdown files to a more permanent folder.

`mx2md` uses a JSON database to track synced files. It automatically detects and updates modified notes in the destination folder and deletes notes that have been removed from Memorix, effectively keeping a local mirror. This setup is useful if you want your notes accessible in more advanced note-taking apps like [Obsidian](https://obsidian.md/).

# Limitations
Currently, `mx2md` cannot:
- Extract notes stored in the Vault, and this is unlikely to change.
- Maintain information about reminders.

# License
`mx2md` is licensed under a 2-clause BSD license.
