import json
import os
 
 
class ResponseLogger:
    def __init__(self, response_file="logs/response_data.json", timestamp_file="logs/response_timestamp.json"):
        self.response_file = response_file
        self.timestamp_file = timestamp_file
 
        # FIX: Auto-create log directories if they don't exist
        for filepath in [self.response_file, self.timestamp_file]:
            dir_path = os.path.dirname(filepath)
            if dir_path:
                os.makedirs(dir_path, exist_ok=True)
 
    def append_to_json_file(self, response_data_holder):
        try:
            if os.path.exists(self.response_file) and os.path.getsize(self.response_file) > 0:
                with open(self.response_file, "r+") as file:
                    try:
                        data = json.load(file)
                    except json.JSONDecodeError:
                        data = []
                    data.append(response_data_holder)
                    file.seek(0)
                    json.dump(data, file, indent=4)
                    file.truncate()
            else:
                with open(self.response_file, "w") as file:
                    json.dump([response_data_holder], file, indent=4)
        except OSError as e:
            print(f"Error accessing file {self.response_file}: {e}")
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
 
    def time_stamp_append_to_json_file(self, response_data_holder):
        try:
            if os.path.exists(self.timestamp_file) and os.path.getsize(self.timestamp_file) > 0:
                with open(self.timestamp_file, "r+") as file:
                    try:
                        data = json.load(file)
                    except json.JSONDecodeError:
                        data = []
                    data.append(response_data_holder)
                    file.seek(0)
                    json.dump(data, file, indent=4)
                    file.truncate()
            else:
                with open(self.timestamp_file, "w") as file:
                    json.dump([response_data_holder], file, indent=4)
        except OSError as e:
            print(f"Error accessing file {self.timestamp_file}: {e}")
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
 