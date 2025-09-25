# command_module.py
from flask import Blueprint, request, jsonify
from helper_func import get_db_connection   # same as in user_module

command_bp = Blueprint("command", __name__, url_prefix="/commands")

@command_bp.route("/", methods=["POST"])
def add_outlet_commands_with_slots():
    try:
        data = request.get_json()
        document_outlet_name = data.get("document_outlet_name")
        commands = data.get("commands", [])

        if not document_outlet_name or not isinstance(commands, list) or not commands:
            return jsonify({"error": "document_outlet_name and commands list are required"}), 400

        conn = get_db_connection()
        cursor = conn.cursor()

        def insert_command(command, parent_id=None):
            command_text = command.get("command_text")
            slots = command.get("slots", [])
            subcommands = command.get("subcommands", [])

            if not command_text:
                return None

            # Insert command
            cursor.execute(
                """
                INSERT INTO outlet_commands (document_outlet_name, command_text, parent_command_id)
                VALUES (%s, %s, %s)
                """,
                (document_outlet_name, command_text, parent_id)
            )
            command_id = cursor.lastrowid

            # Insert slots for this command
            for slot_name in slots:
                cursor.execute(
                    """
                    INSERT INTO outlet_command_slots (command_id, slot_name, required)
                    VALUES (%s, %s, %s)
                    """,
                    (command_id, slot_name, 1)
                )

            # Recursively insert subcommands
            for sub in subcommands:
                insert_command(sub, parent_id=command_id)

            return command_id

        # Insert all root commands
        for cmd in commands:
            insert_command(cmd)

        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({
            "message": "Commands with slots (and subcommands) added successfully",
            "document_outlet_name": document_outlet_name
        }), 201

    except Exception as e:
        print("Error inserting commands:", e)
        return jsonify({"error": str(e)}), 500


# @command_bp.route("/<document_outlet_name>", methods=["GET"])
# def get_outlet_commands(document_outlet_name):
#     try:
#         parent_id = request.args.get("parent_id")  # frontend sends ?parent_id=7

#         conn = get_db_connection()
#         cursor = conn.cursor(dictionary=True)

#         if parent_id:
#             try:
#                 parent_id = int(parent_id)
#             except ValueError:
#                 return jsonify({"error": "Invalid parent_id"}), 400
#             query = """
#                 SELECT c.command_id, c.command_text, c.parent_command_id
#                 FROM outlet_commands c
#                 WHERE c.document_outlet_name = %s AND c.parent_command_id = %s
#             """
#             cursor.execute(query, (document_outlet_name, parent_id))
#         else:
#             query = """
#                 SELECT c.command_id, c.command_text, c.parent_command_id
#                 FROM outlet_commands c
#                 WHERE c.document_outlet_name = %s AND c.parent_command_id IS NULL
#             """
#             cursor.execute(query, (document_outlet_name,))

#         commands = cursor.fetchall()

#         # Fetch slots for each command
#         for cmd in commands:
#             cursor.execute(
#                 """
#                 SELECT slot_id, slot_name, required
#                 FROM outlet_command_slots
#                 WHERE command_id = %s
#                 """,
#                 (cmd["command_id"],)
#             )
#             cmd["slots"] = cursor.fetchall()

#         cursor.close()
#         conn.close()

#         if not commands:
#             return jsonify({"message": "No commands found", "commands": []}), 200

#         return jsonify({
#             "document_outlet_name": document_outlet_name,
#             "parent_id": parent_id if parent_id else "root",
#             "commands": commands
#         }), 200

#     except Exception as e:
#         print("Error fetching commands:", e)
#         return jsonify({"error": str(e)}), 500

@command_bp.route("/<document_outlet_name>", methods=["GET"])
def get_outlet_commands(document_outlet_name):
    try:
        parent_id = request.args.get("parent_id")  # frontend sends ?parent_id=7

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        if parent_id:
            try:
                parent_id = int(parent_id)
            except ValueError:
                return jsonify({"error": "Invalid parent_id"}), 400
            query = """
                SELECT c.command_id, c.command_text, c.parent_command_id
                FROM outlet_commands c
                WHERE c.document_outlet_name = %s AND c.parent_command_id = %s
            """
            cursor.execute(query, (document_outlet_name, parent_id))
        else:
            query = """
                SELECT c.command_id, c.command_text, c.parent_command_id
                FROM outlet_commands c
                WHERE c.document_outlet_name = %s AND c.parent_command_id IS NULL
            """
            cursor.execute(query, (document_outlet_name,))

        commands = cursor.fetchall()

        # Fetch slots and images for each command
        for cmd in commands:
            # Slots
            cursor.execute(
                """
                SELECT slot_id, slot_name, required
                FROM outlet_command_slots
                WHERE command_id = %s
                """,
                (cmd["command_id"],)
            )
            cmd["slots"] = cursor.fetchall()

            # Images
            cursor.execute(
                """
                SELECT image_url
                FROM outlet_command_images
                WHERE command_id = %s
                """,
                (cmd["command_id"],)
            )
            images = cursor.fetchall()
            cmd["images"] = [img["image_url"] for img in images] if images else []

        cursor.close()
        conn.close()

        if not commands:
            return jsonify({"message": "No commands found", "commands": []}), 200

        return jsonify({
            "document_outlet_name": document_outlet_name,
            "parent_id": parent_id if parent_id else "root",
            "commands": commands
        }), 200

    except Exception as e:
        print("Error fetching commands:", e)
        return jsonify({"error": str(e)}), 500



# @command_bp.route("/rootcommands", methods=["GET"])
# def get_root_commands():
#     try:
#         conn = get_db_connection()
#         cursor = conn.cursor(dictionary=True)
#         document_outlet_name = request.args.get("document_outlet_name")  
#         # Fetch all commands with parent_command_id IS NULL (root commands)
#         query = """
#             SELECT command_id, command_text
#             FROM outlet_commands
#             WHERE parent_command_id IS NULL and document_outlet_name = %s
#             ORDER BY command_text
#         """
#         cursor.execute(query, (document_outlet_name,))
#         rows = cursor.fetchall()

#         cursor.close()
#         conn.close()

#         if not rows:
#             return jsonify({"message": "No root commands found", "rootcommands": []}), 200

#         # Send both name and parent_id
#         rootcommands = [{"command_text": row["command_text"], "parent_id": row["command_id"]} for row in rows]

#         return jsonify({
#             "rootcommands": rootcommands
#         }), 200

#     except Exception as e:
#         print("Error fetching root commands:", e)
#         return jsonify({"error": str(e)}), 500

@command_bp.route("/rootcommands", methods=["GET"])
def get_root_commands():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        document_outlet_name = request.args.get("document_outlet_name")  

        # Fetch all commands with parent_command_id IS NULL (root commands)
        query = """
            SELECT command_id, command_text
            FROM outlet_commands
            WHERE parent_command_id IS NULL AND document_outlet_name = %s
            ORDER BY command_text
        """
        cursor.execute(query, (document_outlet_name,))
        rows = cursor.fetchall()

        # Attach images for each root command
        rootcommands = []
        for row in rows:
            cursor.execute(
                "SELECT image_url FROM outlet_command_images WHERE command_id = %s",
                (row["command_id"],)
            )
            images = cursor.fetchall()
            image_list = [img["image_url"] for img in images] if images else []

            rootcommands.append({
                "command_text": row["command_text"],
                "parent_id": row["command_id"],
                "images": image_list
            })

        cursor.close()
        conn.close()

        if not rootcommands:
            return jsonify({"message": "No root commands found", "rootcommands": []}), 200

        return jsonify({
            "rootcommands": rootcommands
        }), 200

    except Exception as e:
        print("Error fetching root commands:", e)
        return jsonify({"error": str(e)}), 500

    
@command_bp.route("/delete/<int:command_id>", methods=["DELETE"])
def delete_command(command_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Delete slots first
        cursor.execute(
            "DELETE FROM outlet_command_slots WHERE command_id = %s",
            (command_id,)
        )

        # Delete the command; subcommands will be automatically deleted due to ON DELETE CASCADE
        cursor.execute(
            "DELETE FROM outlet_commands WHERE command_id = %s",
            (command_id,)
        )
        conn.commit()

        cursor.close()
        conn.close()

        return jsonify({
            "message": f"Command {command_id} and its subcommands (if any) deleted successfully."
        }), 200

    except Exception as e:
        print("Error deleting command:", e)
        return jsonify({"error": str(e)}), 500


@command_bp.route("/delete-slots", methods=["DELETE"])
def delete_slots():
    try:
        data = request.get_json()
        slot_ids = data.get("slot_ids")

        if not slot_ids:
            return jsonify({"error": "slot_ids list is required"}), 400

        # If a single ID is sent as integer, convert to list
        if isinstance(slot_ids, int):
            slot_ids = [slot_ids]
        elif not isinstance(slot_ids, list):
            return jsonify({"error": "slot_ids must be an integer or list of integers"}), 400

        conn = get_db_connection()
        cursor = conn.cursor()

        # Delete all slots in one query
        format_strings = ','.join(['%s'] * len(slot_ids))
        cursor.execute(
            f"DELETE FROM outlet_command_slots WHERE slot_id IN ({format_strings})",
            tuple(slot_ids)
        )
        conn.commit()

        cursor.close()
        conn.close()

        return jsonify({
            "message": f"Slots {slot_ids} deleted successfully."
        }), 200

    except Exception as e:
        print("Error deleting slots:", e)
        return jsonify({"error": str(e)}), 500

from flask import request, jsonify, current_app  # use current_app instead of app
from werkzeug.utils import secure_filename
import os
from file_utils import allowed_file, UPLOAD_FOLDER
from helper_func import get_db_connection

@command_bp.route("/upload-image", methods=["POST"])
def upload_command_image():
    try:
        command_id = request.form.get("command_id")
        if not command_id:
            return jsonify({"error": "command_id is required"}), 400

        if "image" not in request.files:
            return jsonify({"error": "No image file provided"}), 400

        file = request.files["image"]
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)

            # safer to use current_app.config here
            save_path = os.path.join(current_app.config["UPLOAD_FOLDER"], filename)
            file.save(save_path)

            # store relative path instead of absolute path
            relative_path = os.path.relpath(save_path, start=os.getcwd())

            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO outlet_command_images (command_id, image_url) VALUES (%s, %s)",
                (command_id, relative_path)
            )
            conn.commit()
            cursor.close()
            conn.close()

            return jsonify({
                "message": "Image uploaded successfully",
                "command_id": command_id,
                "image_url": relative_path
            }), 201

        return jsonify({"error": "Invalid file type"}), 400

    except Exception as e:
        return jsonify({"error": str(e)}), 500


