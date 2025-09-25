# command_module.py
from flask import Blueprint, request, jsonify
from helper_func import get_db_connection   # same as in user_module

command_bp = Blueprint("command", __name__, url_prefix="/commands")

# ------------------------------
# Add commands for an outlet
# ------------------------------


# @command_bp.route("/", methods=["POST"])
# def add_outlet_commands_with_slots():
#     try:
#         data = request.get_json()
#         document_outlet_name = data.get("document_outlet_name")
#         commands = data.get("commands", [])

#         if not document_outlet_name or not isinstance(commands, list) or not commands:
#             return jsonify({"error": "document_outlet_name and commands list are required"}), 400

#         conn = get_db_connection()
#         cursor = conn.cursor()

#         for cmd in commands:
#             command_text = cmd.get("command_text")
#             rootcommand = cmd.get("rootcommand")   # NEW FIELD
#             slots = cmd.get("slots", [])

#             if not command_text or not rootcommand:
#                 continue

#             # Insert command with rootcommand
#             cursor.execute(
#                 """
#                 INSERT INTO outlet_commands (document_outlet_name, command_text, rootcommand) 
#                 VALUES (%s, %s, %s)
#                 """,
#                 (document_outlet_name, command_text, rootcommand)
#             )
#             command_id = cursor.lastrowid

#             # Insert slots for this command
#             for slot_name in slots:
#                 cursor.execute(
#                     """
#                     INSERT INTO outlet_command_slots (command_id, slot_name, required) 
#                     VALUES (%s, %s, %s)
#                     """,
#                     (command_id, slot_name, 1)
#                 )

#         conn.commit()
#         cursor.close()
#         conn.close()

#         return jsonify({
#             "message": "Commands with slots added successfully",
#             "document_outlet_name": document_outlet_name,
#             "commands": commands
#         }), 201

#     except Exception as e:
#         print("Error inserting commands:", e)
#         return jsonify({"error": str(e)}), 500

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
#         rootcommand = request.args.get("rootcommand")  # frontend sends ?rootcommand=appointment

#         conn = get_db_connection()
#         cursor = conn.cursor(dictionary=True)

#         if rootcommand:
#             query = """
#                 SELECT command_id, command_text, rootcommand
#                 FROM outlet_commands
#                 WHERE document_outlet_name = %s AND rootcommand = %s
#             """
#             cursor.execute(query, (document_outlet_name, rootcommand))
#         else:
#             query = """
#                 SELECT command_id, command_text, rootcommand
#                 FROM outlet_commands
#                 WHERE document_outlet_name = %s
#             """
#             cursor.execute(query, (document_outlet_name,))

#         rows = cursor.fetchall()

#         cursor.close()
#         conn.close()

#         if not rows:
#             return jsonify({"message": "No commands found", "commands": []}), 200

#         return jsonify({
#             "document_outlet_name": document_outlet_name,
#             "rootcommand": rootcommand if rootcommand else "all",
#             "commands": rows
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

        # Fetch slots for each command
        for cmd in commands:
            cursor.execute(
                """
                SELECT slot_id, slot_name, required
                FROM outlet_command_slots
                WHERE command_id = %s
                """,
                (cmd["command_id"],)
            )
            cmd["slots"] = cursor.fetchall()

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


    
# ------------------------------
# Get unique root commands
# ------------------------------
# @command_bp.route("/rootcommands", methods=["GET"])
# def get_root_commands():
#     try:
#         conn = get_db_connection()
#         cursor = conn.cursor(dictionary=True)

#         query = """
#             SELECT DISTINCT rootcommand
#             FROM outlet_commands
#             WHERE rootcommand IS NOT NULL
#             ORDER BY rootcommand
#         """
#         cursor.execute(query)
#         rows = cursor.fetchall()

#         cursor.close()
#         conn.close()

#         rootcommands = [row["rootcommand"] for row in rows]

#         if not rootcommands:
#             return jsonify({"message": "No rootcommands found", "rootcommands": []}), 200

#         return jsonify({
#             "rootcommands": rootcommands
#         }), 200

#     except Exception as e:
#         print("Error fetching rootcommands:", e)
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
            WHERE parent_command_id IS NULL and document_outlet_name = %s
            ORDER BY command_text
        """
        cursor.execute(query, (document_outlet_name,))
        rows = cursor.fetchall()

        cursor.close()
        conn.close()

        if not rows:
            return jsonify({"message": "No root commands found", "rootcommands": []}), 200

        # Send both name and parent_id
        rootcommands = [{"command_text": row["command_text"], "parent_id": row["command_id"]} for row in rows]

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
