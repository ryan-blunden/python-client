import requests
from requests_futures.sessions import FuturesSession
import json
import os
from enum import Enum

try:
  set
except NameError:
  from sets import Set as set


class Doppler:
  
  class Priority(Enum):
    Local = 1
    Remote = 2 
  
  host = os.getenv('DOPPLER_HOST', "https://api.doppler.market")
  max_retries = 10
  remote_keys = {}
  
  
  def __init__(self, data):
    
    if data.get("api_key") is None:
      raise ValueError("Please provide an 'api_key' on initialization.")
      
    if data.get("pipeline") is None:
      raise ValueError("Please provide an 'pipeline' on initialization.")
      
    if data.get("environment") is None:
      raise ValueError("Please provide an 'environment' on initialization.")
      
    self.api_key = str(data.get("api_key"))
    self.pipeline = str(data.get("pipeline"))
    self.environment = str(data.get("environment"))
    self.defaultPriority = data.get("priority", Doppler.Priority.Remote)
    self.send_local_keys = data.get("send_local_keys", True)
    self.ignore_keys = set(data.get("ignore_keys", []))
    self.override_local_keys = data.get("override_local_keys", False)
    self.startup()
  
  
  
  def startup(self):
    keys_to_send = {}
    local_keys = os.environ.copy()
    
    if self.send_local_keys:   
      for key in local_keys:
        value = local_keys[key]
        
        if key not in self.ignore_keys:
          keys_to_send[key] = value
    
    response = self._request("/fetch_keys", {
      "local_keys": keys_to_send
    })
    
    if response:
      self.remote_keys = response["keys"]
      self.override_keys()
      

      
  def get(self, key_name, priority=None):
      priority = priority or self.defaultPriority
      
      if key_name in self.remote_keys:
        if priority == Doppler.Priority.Local:
          return os.getenv(key_name, self.remote_keys.get(key_name))
          
        return self.remote_keys[key_name]
      
      if key_name not in self.ignore_keys:
        self._request("/missing_key", {
          "key_name": key_name
        }, isAsync=True)
      
      return os.getenv(key_name)
    
  
  def override_keys(self):
    if self.override_local_keys == False: return
    
    override_keys = self.override_local_keys
    
    if override_keys == True:
      override_keys = self.remote_keys.keys()
    
    for key_name in override_keys:
      if key_name in self.remote_keys:
        os.environ[key_name] = self.remote_keys.get(key_name)
  
  
  def _request(self, endpoint, body, retry_count=0, isAsync=False):
    try:
      endpoint = self.host + "/environments/" + self.environment + endpoint
      requester = requests
      
      if isAsync:
        requester = FuturesSession()
      
      response = requester.post(endpoint, json=body, headers={
        "api-key": self.api_key,
        "pipeline": self.pipeline
      }, timeout=1500)
      
      if response is None or isAsync: return None
      
      response = response.json()
      
      if not response["success"]:
        raise ValueError(". ".join(response["messages"]))
        
      return response
      
    except requests.exceptions.RequestException:
      retry_count += 1
      
      if retry_count > self.max_retries: 
        print("DOPPLER: Failed to reach Doppler servers after " + retry_count + " retries...\n")
        return None
      
      return self._request(endpoint, body, retry_count)
