from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt



def main():


    folder_path = Path("Some_Example_GPS_Files 2/") # Replace with the actual path
    for file_path in folder_path.iterdir():
        if file_path.is_file(): 
            try:
                with open(file_path, 'r') as f:
                    content = f.read()
                    print(f"Content of {file_path.name}:\n{content}\n---")
            except Exception as e:
                print(f"Error reading {file_path.name}: {e}")





if __name__ == "__main__":
    main()

        
    





    
    

if __name__ == "__main__":
    main()