import json
import os


class ResponseLogger:
    def __init__(self, response_file="logs/response_data.json", timestamp_file="logs/response_timestamp.json"):
        self.response_file = response_file
        self.timestamp_file = timestamp_file

    def append_to_json_file(self, response_data_holder):
        try:
            # Check if the file exists and is non-empty
            if os.path.exists(self.response_file) and os.path.getsize(self.response_file) > 0:
                # File exists and contains data, so load it and append
                with open(self.response_file, "r+") as file:
                    try:
                        # Load existing data into a list
                        data = json.load(file)
                    except json.JSONDecodeError:
                        # If the file is empty or has invalid JSON, initialize as an empty list
                        data = []
                    # Append the new dictionary
                    data.append(response_data_holder)
                    # Go back to the beginning of the file and truncate it
                    file.seek(0)
                    json.dump(data, file, indent=4)
                    file.truncate()  # Remove any remaining old content
            else:
                # If the file doesn't exist or is empty, create it with an initial list
                with open(self.response_file, "w") as file:
                    json.dump([response_data_holder], file, indent=4)
        except OSError as e:
            print(f"Error accessing file {self.response_file}: {e}")
        except Exception as e:
            print(f"An unexpected error occurred: {e}")

    def time_stamp_append_to_json_file(self, response_data_holder):
        try:
            # Check if the file exists and is non-empty
            if os.path.exists(self.timestamp_file) and os.path.getsize(self.timestamp_file) > 0:
                # File exists and contains data, so load it and append
                with open(self.timestamp_file, "r+") as file:
                    try:
                        # Load existing data into a list
                        data = json.load(file)
                    except json.JSONDecodeError:
                        # If the file is empty or has invalid JSON, initialize as an empty list
                        data = []
                    # Append the new dictionary
                    data.append(response_data_holder)
                    # Go back to the beginning of the file and truncate it
                    file.seek(0)
                    json.dump(data, file, indent=4)
                    file.truncate()  # Remove any remaining old content
            else:
                # If the file doesn't exist or is empty, create it with an initial list
                with open(self.timestamp_file, "w") as file:
                    json.dump([response_data_holder], file, indent=4)
        except OSError as e:
            print(f"Error accessing file {self.timestamp_file}: {e}")
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
