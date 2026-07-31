import httpx
import json
import sys

API_URL = "http://localhost:8001/chat"
THREAD_ID = "cli-test-session"

def main():
    print("=====================================================")
    print(" GovStay Agent CLI Tester")
    print(" Type 'quit' or 'exit' to stop.")
    print("=====================================================\n")

    while True:
        try:
            user_input = input("\nYou: ")
            if user_input.lower() in ['quit', 'exit']:
                break
                
            if not user_input.strip():
                continue

            print("Agent: ", end="", flush=True)
            
            with httpx.stream("POST", API_URL, json={"message": user_input, "thread_id": THREAD_ID}, timeout=60.0) as response:
                for line in response.iter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str == "[DONE]":
                            break
                        try:
                            data = json.loads(data_str)
                            # Print text chunk without newline
                            if "text" in data:
                                print(data["text"], end="", flush=True)
                                
                            # If there's a UI sync event, print it on a new line so we can see it
                            if "ui_state" in data and data["ui_state"]:
                                print(f"\n\n[SYSTEM UI SYNC TRIGGERED: {data['ui_state']}]", end="")
                        except json.JSONDecodeError:
                            pass
            print() # Final newline after response finishes

        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"\nError: {e}")

if __name__ == "__main__":
    main()
