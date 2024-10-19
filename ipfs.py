import requests
import json

def pin_to_ipfs(data):
	assert isinstance(data,dict), f"Error pin_to_ipfs expects a dictionary"
	#YOUR CODE HERE
	json_data = json.dumps(data)
	url = "https://api.pinata.cloud/pinning/pinJSONToIPFS"
	
	headers = {
	'pinata_api_key': '6f5625c5730c347267a2',
	'pinata_secret_api_key': '4c3e0292a8362339cf6318c5a6679d7be041c3119065130ee6d6d45ff3c01bee',
	'Content-Type': 'application/json'
	}
	
	files = {
	'file': ('data.json', json_data)
	}
	
	response = requests.post(url, headers=headers, data=json_data)
	
	if response.status_code == 200:
		cid = response.json()['IpfsHash']
	else:
		raise Exception(f"Failed to pin to IPFS: {response.text}")
	
	return cid

def get_from_ipfs(cid,content_type="json"):
	assert isinstance(cid,str), f"get_from_ipfs accepts a cid in the form of a string"
	#YOUR CODE HERE	
	
	url = f"https://gateway.pinata.cloud/ipfs/{cid}"
	
	response = requests.get(url)
	
	if response.status_code == 200:
		if content_type == "json":
			data = json.loads(response.text)
		else:
			data = response.text
	else:
		raise Exception(f"Failed to retrieve data from IPFS: {response.text}")
	
	
	assert isinstance(data,dict), f"get_from_ipfs should return a dict"
	return data
