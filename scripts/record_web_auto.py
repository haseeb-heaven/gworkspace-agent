
import time
import subprocess
import os
import sys
import scripts.obs_controller as obs_controller

def run():
    print("--- WEB GUI DEMO AUTOMATION (Managed by Agent) ---")
    
    # Signal file to know when agent is done interacting
    done_file = os.path.join(os.getcwd(), "web_done.tmp")
    if os.path.exists(done_file):
        try: os.remove(done_file)
        except: pass

    print("Launching Web Server...")
    # Run server in a way that we can capture its output if needed
    web_proc = subprocess.Popen([sys.executable, "gws_gui_web.py"], 
                               stdout=subprocess.PIPE, 
                               stderr=subprocess.STDOUT,
                               text=True)
    
    print("Waiting for server to be ready (10s)...")
    time.sleep(10)
    
    print("Starting OBS recording...")
    obs_controller.start_recording()
    
    print("\n[AGENT_SIGNAL] WEB_SERVER_READY_AT_7860")
    print("Waiting for Agent to perform interactions via Chrome DevTools...")
    
    # Wait for the agent to create the signal file
    start_time = time.time()
    while not os.path.exists(done_file):
        time.sleep(1)
        if time.time() - start_time > 300: # 5 min safety
            print("Error: Web interaction timed out.")
            break
            
    print("Agent interaction complete. Waiting 5s for UI to settle...")
    time.sleep(5)
    
    print("Stopping OBS recording...")
    obs_controller.stop_recording()
    
    web_proc.terminate()
    if os.path.exists(done_file):
        try: os.remove(done_file)
        except: pass
        
    print("Web GUI Demo Action Finished.")
    return True

if __name__ == "__main__":
    run()
