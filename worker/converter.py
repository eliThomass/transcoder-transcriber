import json

def convertToSrt(json_file, srt_file):

    
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
