from web3 import Web3
from web3.contract import Contract
from web3.providers.rpc import HTTPProvider
import requests
import json
import time

bayc_address = "0xBC4CA0EdA7647A8aB7C2061c2E118A18a936f13D"
contract_address = Web3.toChecksumAddress(bayc_address)

#You will need the ABI to connect to the contract
#The file 'abi.json' has the ABI for the bored ape contract
#In general, you can get contract ABIs from etherscan
#https://api.etherscan.io/api?module=contract&action=getabi&address=0xBC4CA0EdA7647A8aB7C2061c2E118A18a936f13D
with open('/home/codio/workspace/abi.json', 'r') as f:
	abi = json.load(f) 

############################
#Connect to an Ethereum node
token = "CFboJVFkJcwY2VYlaWWPxpf_23CjpB9Z"
api_url = "https://eth-mainnet.alchemyapi.io/v2/{token}" #YOU WILL NEED TO TO PROVIDE THE URL OF AN ETHEREUM NODE
provider = HTTPProvider(api_url)
web3 = Web3(provider)

if not web3.is_connected():
  raise ConnectionError(f"Unable to connect to Ethereum node at {api_url}")

contract = web3.eth.contract(address=contract_address, abi=abi)

def get_ape_info(apeID):
	assert isinstance(apeID,int), f"{apeID} is not an int"
	assert 1 <= apeID, f"{apeID} must be at least 1"
	
	data = {'owner': "", 'image': "", 'eyes': "" }
	
	#YOUR CODE HERE	
	# get the current owner of the specified ape
	try:
		owner = contract.functions.ownerOf(apeID).call()
		data['owner'] = owner
	except Exception as err:
		raise ValueError(f"Failed to get owner for Ape ID {apeID}: {err}")
  
	# get the token uri for metadata
	try:
		token_uri = contract.functions.tokenURI(apeID).call()
		if token_uri.startswith("ipfs://"):
			token_uri = token_uri.replace("ipfs://", "https://ipfs.io/ipfs/")
  
	except Exception as err:
		raise ValueError(f"Failed to get tokenURI for Ape ID {apeID}: {err}")

	# fetch metadata from ipfs
	try:
		response = requests.get(token_uri, timeout=20)
		if response.status_code == 200:
		      metadata = response.json()
		      # extract the image URI
		      data['image'] = metadata.get('image', "")
		      # extract the eye attribute
		      attributes = metadata.get('attributes', [])
		      for attribute in attributes:
			if attribute.get('trait_type') == 'Eyes':
				data['eyes'] = attribute.get('value', "")
				break
	    else:
	      raise ValueError(f"Failed to fetch metadata from IPFS, status code: {response.status_code}")
	except Exception as err:
		raise ValueError(f"Failed to fetch metadata from IPFS for Ape ID {apeID}: {err}")




	assert isinstance(data,dict), f'get_ape_info{apeID} should return a dict' 
	assert all( [a in data.keys() for a in ['owner','image','eyes']] ), f"return value should include the keys 'owner','image' and 'eyes'"
	return data

