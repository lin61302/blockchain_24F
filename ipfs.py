import requests
import json

def pin_to_ipfs(data):
	assert isinstance(data,dict), f"Error pin_to_ipfs expects a dictionary"
	#YOUR CODE HERE
  	json_data = json.dumps(data)
  	url = "https://ipfs.infura.io:5001/api/v0/add"

	headers = {
        'Authorization': f'Bearer deb5b8898f824b03947c36b9cd8d15d2'
    }

	files = {
        'file': ('data.json', json_data)
    }
	
	response = requests.post(url, headers=headers, files=files)

	if response.status_code == 200:
        	cid = response.json()['Hash']
    	else:
        	raise Exception(f"Failed to pin to IPFS: {response.text}")

	return cid

def get_from_ipfs(cid,content_type="json"):
	assert isinstance(cid,str), f"get_from_ipfs accepts a cid in the form of a string"
	#YOUR CODE HERE	

	url = f"https://ipfs.infura.io:5001/api/v0/cat?arg={cid}"

	response = requests.post(url)

	if response.status_code == 200:
        	if content_type == "json":
            		data = json.loads(response.text)
        	else:
            		data = response.text
    	else:
        	raise Exception(f"Failed to retrieve data from IPFS: {response.text}")

	assert isinstance(data,dict), f"get_from_ipfs should return a dict"
	return data
