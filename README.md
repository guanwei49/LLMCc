# LLMCc: Leveraging LLMs for Compliance Checking in Business Process Models #

Official Implementation of "LLMCc: Leveraging LLMs for Compliance Checking in Business Process Models"


## Code Outputs
- ```output_com.txt``` contains the code outputs for compliant process models located in ```.\LPD4VR-master\compliance.```

- ```output_vio.txt``` contains the code outputs for non-compliant (violation) process models located in ```.\LPD4VR-master\violation.```


## Using Our Code to Reproduce the Results

1. Create conda environment.

```
 conda install --yes --file requirements.txt # You may need to downgrade the torch using pip to match the CUDA version
```

2. Evaluate on test dataset located in folder ```LPD4VR-master```.

- Set the following variations in ```main.py```
   ```
  client = OpenAI( 
    api_key = os.environ.get("OPENAI_API_KEY")  # You can also pass the api_key as an argument directly
  )

  rule_file = # i.e., r".\LPD4VR-master\rules.txt";  Path to the file containing the regulations
  bpmn_folder_path = # i.e., r".\LPD4VR-master\violance"; Directory path containing the BPMN 2.0 business process models 
   ```
  
- Run ```python main.py``` from the root directory. 