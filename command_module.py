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

#         # Fetch slots and images for each command
#         for cmd in commands:
#             # Slots
#             cursor.execute(
#                 """
#                 SELECT slot_id, slot_name, required
#                 FROM outlet_command_slots
#                 WHERE command_id = %s
#                 """,
#                 (cmd["command_id"],)
#             )
#             cmd["slots"] = cursor.fetchall()

#             # Images
#             cursor.execute(
#                 """
#                 SELECT image_url
#                 FROM outlet_command_images
#                 WHERE command_id = %s
#                 """,
#                 (cmd["command_id"],)
#             )
#             images = cursor.fetchall()
#             cmd["images"] = [img["image_url"] for img in images] if images else []

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

            # Images (include id + url)
            cursor.execute(
                """
                SELECT image_id, image_url
                FROM outlet_command_images
                WHERE command_id = %s
                """,
                (cmd["command_id"],)
            )
            cmd["images"] = cursor.fetchall()  # already dicts (id + url)

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
#             WHERE parent_command_id IS NULL AND document_outlet_name = %s
#             ORDER BY command_text
#         """
#         cursor.execute(query, (document_outlet_name,))
#         rows = cursor.fetchall()

#         # Attach images for each root command
#         rootcommands = []
#         for row in rows:
#             cursor.execute(
#                 "SELECT image_url FROM outlet_command_images WHERE command_id = %s",
#                 (row["command_id"],)
#             )
#             images = cursor.fetchall()
#             image_list = [img["image_url"] for img in images] if images else []

#             rootcommands.append({
#                 "command_text": row["command_text"],
#                 "parent_id": row["command_id"],
#                 "images": image_list
#             })

#         cursor.close()
#         conn.close()

#         if not rootcommands:
#             return jsonify({"message": "No root commands found", "rootcommands": []}), 200

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
                "SELECT image_id, image_url FROM outlet_command_images WHERE command_id = %s",
                (row["command_id"],)
            )
            images = cursor.fetchall()
            image_list = images if images else []

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
    

@command_bp.route("/subcommand", methods=["POST"])
def add_subcommand_with_slots():
    try:
        data = request.get_json()
        parent_command_id = data.get("parent_command_id")
        command_text = data.get("command_text")
        slots = data.get("slots", [])
        subcommands = data.get("subcommands", [])

        if not parent_command_id or not command_text:
            return jsonify({"error": "parent_command_id and command_text are required"}), 400

        conn = get_db_connection()
        cursor = conn.cursor()

        # Get document_outlet_name from parent (to keep consistency)
        cursor.execute(
            "SELECT document_outlet_name FROM outlet_commands WHERE command_id = %s",
            (parent_command_id,)
        )
        parent = cursor.fetchone()
        if not parent:
            return jsonify({"error": "Parent command not found"}), 404

        document_outlet_name = parent[0]

        def insert_command(command, parent_id):
            cmd_text = command.get("command_text")
            cmd_slots = command.get("slots", [])
            cmd_subs = command.get("subcommands", [])

            cursor.execute(
                """
                INSERT INTO outlet_commands (document_outlet_name, command_text, parent_command_id)
                VALUES (%s, %s, %s)
                """,
                (document_outlet_name, cmd_text, parent_id)
            )
            command_id = cursor.lastrowid

            # Insert slots
            for slot_name in cmd_slots:
                cursor.execute(
                    """
                    INSERT INTO outlet_command_slots (command_id, slot_name, required)
                    VALUES (%s, %s, %s)
                    """,
                    (command_id, slot_name, 1)
                )

            # Recursive for further subcommands
            for sub in cmd_subs:
                insert_command(sub, command_id)

            return command_id

        # Insert new subcommand under parent
        new_command_id = insert_command(
            {"command_text": command_text, "slots": slots, "subcommands": subcommands},
            parent_command_id
        )

        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({
            "message": "Subcommand with slots added successfully",
            "parent_command_id": parent_command_id,
            "new_command_id": new_command_id
        }), 201

    except Exception as e:
        print("Error inserting subcommand:", e)
        return jsonify({"error": str(e)}), 500


@command_bp.route("/slots", methods=["POST"])
def add_slots_to_command():
    try:
        data = request.get_json()
        command_id = data.get("command_id")
        slots = data.get("slots", [])

        if not command_id or not isinstance(slots, list) or not slots:
            return jsonify({"error": "command_id and slots list are required"}), 400

        conn = get_db_connection()
        cursor = conn.cursor()

        # Check if command exists
        cursor.execute("SELECT command_id FROM outlet_commands WHERE command_id = %s", (command_id,))
        if not cursor.fetchone():
            return jsonify({"error": "Command not found"}), 404

        # Insert new slots
        for slot_name in slots:
            cursor.execute(
                """
                INSERT INTO outlet_command_slots (command_id, slot_name, required)
                VALUES (%s, %s, %s)
                """,
                (command_id, slot_name, 1)
            )

        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({
            "message": "Slots added successfully",
            "command_id": command_id,
            "slots_added": slots
        }), 201

    except Exception as e:
        print("Error adding slots:", e)
        return jsonify({"error": str(e)}), 500

@command_bp.route("/delete-image", methods=["DELETE"])
def delete_command_image():
    try:
        data = request.get_json()
        command_id = data.get("command_id")
        image_id = data.get("image_id")         # single
        image_ids = data.get("image_ids", [])   # multiple

        if not command_id:
            return jsonify({"error": "command_id is required"}), 400

        # Normalize to a list of IDs to delete
        ids_to_delete = []
        if image_ids:
            ids_to_delete = image_ids
        elif image_id:
            ids_to_delete = [image_id]
        else:
            return jsonify({"error": "Provide image_id or image_ids"}), 400

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        deleted_images = []

        for img_id in ids_to_delete:
            cursor.execute(
                "SELECT image_id, image_url FROM outlet_command_images WHERE image_id = %s AND command_id = %s",
                (img_id, command_id)
            )
            image = cursor.fetchone()
            if not image:
                continue  # skip if not found

            image_path = image["image_url"]
            image_db_id = image["image_id"]

            # Delete from DB
            cursor.execute(
                "DELETE FROM outlet_command_images WHERE image_id = %s AND command_id = %s",
                (image_db_id, command_id)
            )
            conn.commit()

            # Delete from filesystem
            abs_path = os.path.join(os.getcwd(), image_path)
            if os.path.exists(abs_path):
                os.remove(abs_path)

            deleted_images.append(image_path)

        cursor.close()
        conn.close()

        if not deleted_images:
            return jsonify({"error": "No images were found or deleted"}), 404

        return jsonify({
            "message": f"{len(deleted_images)} image(s) deleted successfully",
            "command_id": command_id,
            "deleted_images": deleted_images
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500



