import os
import json
import re
import time

from elasticsearch import Elasticsearch
from elasticsearch import client

run_file_path = "run-files/"
run_f_name = "_res_file.txt"

topic_path = "../airs2017-collection/topic/"
auto_gen_methods_path = "auto-generation/queries/"

PORT = 9200
INDEX = "ussc"

es = Elasticsearch(urls='http://localhost', port=PORT, timeout=600)
es_client = client.IndicesClient(es)


def remove_stop(text):
  a_bod = {
    "analyzer": "stop",
    "text": text
  }
  final_text = ""
  res = es_client.analyze(index=INDEX, body=a_bod)

  seen_terms = []
  for i in range(len(res["tokens"])):
    if res["tokens"][i]["token"] not in seen_terms:
    	seen_terms.append(res["tokens"][i]["token"])
    	final_text = final_text + res["tokens"][i]["token"] + " "

  return final_text

def clean_text(text):
	return re.sub('[^a-zA-Z0-9]+', ' ', text).lower()

def get_numbers(text):
  nums = re.findall('[0-9]+', text)
  seen = set()
  ret = ""
  for num in nums:
      if num not in seen:
          seen.add(num)
          ret = ret + num + " "
  return ret.lstrip().rstrip()

def write_results_to_file(res, topic, file, desc, exclude):
	rank = 0
	for j in range(len(res['hits']['hits'])):
		hit_id = res['hits']['hits'][j]['_id']
		if int(hit_id) == exclude:
			continue
		else:
			line = str(topic) + " 0 " + str(hit_id) + \
			 " " + str(rank) + " " + str(res['hits']['hits'][j]['_score']) + " " + desc + "\n"
			rank += 1
			file.write(line)

def get_res(text):
	body = {
		"_source" : ["id"],
		"from": 0, "size": 10,
		"query" : {
			"match" : {
				"plain_text" : text
			}
		}
	}
	# print(body)
	return es.search(index=INDEX, body=body)

def create_run_file(run_name):
	run_file = open(run_file_path + run_name + run_f_name,'w')

	for topic in range(1, 2):
		print("Topic -", topic, "- runname -", run_name)
		topic_case_id = 0
		skip_write = False
		topic_file_name = topic_path + str(topic) + ".json"
		with open(topic_file_name) as topic_file:

			topic_data = json.load(topic_file)
			topic_case_id = topic_data["case_id"]

			res = None

			if run_name == "toppar":
				para = topic_data['citing_paragraph']
				for	extract in topic_data['case_extract']:
					para = para.replace(extract, "")

				# print(para)
				para = clean_text(para)
				# print("Clean -", para)
				numbers = get_numbers(para)
				# print("Num -", numbers)
				para = remove_stop(para)
				para = para + " " + numbers
				# print(para)
				res = get_res(para)

			elif run_name == "topsen":
				sentence = topic_data['citing_sentence']
				for	extract in topic_data['case_extract']:
					sentence = sentence.replace(extract, "")
				sentence = clean_text(sentence)
				numbers = get_numbers(sentence)
				sentence = remove_stop(sentence)
				sentence = sentence + " " + numbers
				# print(sentence)
				res = get_res(sentence)

			elif run_name == "adhockey":
				keyword_sen = ""
				for keyword in topic_data["relevant_keywords"]:
					keyword_sen += keyword + " "
				res = get_res(keyword_sen)

			else:
				if "adhocbool" in run_name:
					run_num = int(run_name[-1]) - 1
					try:
						query = topic_data["es_query"][run_num]

						# exclude topic case from es results
						query["_source"] = ["id"]
						query["from"] = 0
						query["size"] = 1000
						res = es.search(index=INDEX, body=query)
					except:
						skip_write = True
						# print("No boolean manual query for topic", topic, "- num-", run_num)

				elif "adhocsim" in run_name:
					run_num = int(run_name[-1]) - 1
					try:
						qry = topic_data["query"][run_num]
						qry = qry.replace("AND", "", -1)
						qry = qry.replace("OR", "", -1)
						qry = qry.replace("(", "", -1)
						qry = qry.replace(")", "", -1)
						qry = qry.replace("\"", "", -1)
						print(qry)
						res = get_res(qry)
					except:
						skip_write = True
						# print("No simple manual query for topic", topic, "- num-", run_num)

				elif "plm" in run_name:
					run_num = 0
					smooth = 0
					# get measure from name
					measure = ""

					if run_name[-2].isdigit():
						smooth = int(run_name[-2:])
						if run_name[-5].isdigit():
							run_num = int(run_name[-5:-3]) - 1
							measure = run_name[:-5]
						else:
							run_num = int(run_name[-4]) - 1
							measure = run_name[:-4]
					else:
						smooth = int(run_name[-1])
						if run_name[-4].isdigit():
							run_num = int(run_name[-4:-2]) - 1
							measure = run_name[:-4]
						else:
							run_num = int(run_name[-3]) - 1
							measure = run_name[:-3]

					# print("Topic -", topic, "- runname -", run_name, "- measure -", measure, "- run_num -", run_num, "- smooth -", smooth)
					p_f_name = auto_gen_methods_path + str(topic) + "_" + measure + "_" + str(smooth) +  "_auto_query_terms.json"
					with open(p_f_name) as proportion_file:
						proportion_data = json.load(proportion_file)

						sentence = ""
						for term in proportion_data["auto_generated_queries"]["query"][run_num]["terms"]:
							sentence  = sentence + " " + term
						res = get_res(sentence)

				else:
					# deal with proportions
					run_num = 0
					# get measure from name
					measure = ""
					if run_name[-2].isdigit():
						run_num = int(run_name[-2:]) - 1
						measure = run_name[:-2]
					else:
						run_num = int(run_name[-1:]) - 1
						measure = run_name[:-1]

					p_f_name = auto_gen_methods_path + str(topic) + "_" + measure +  "_auto_query_terms.json"
					with open(p_f_name) as proportion_file:
						proportion_data = json.load(proportion_file)

						sentence = ""
						for term in proportion_data["auto_generated_queries"]["query"][run_num]["terms"]:
							sentence  = sentence + " " + term
						res = get_res(sentence)

			if not skip_write:
				write_results_to_file(res, topic, run_file, run_name, topic_case_id)

def main():
	start = time.time()

	runs = ["adhocbool1", "adhocbool2", "adhocbool3", "adhocsim1", "adhocsim2", "adhocsim3", "topsen", "toppar", "adhockey"]
	base = ["idfs", "idfp", "plms", "plmp", "klis", "klip"]
	for run in base:
		for i in range(1, 12):
			if "plm" in run:
				for j in range(1, 11):
					runs.append(run + str(i) + "_" + str(j))
			else:
				runs.append(run + str(i))

	for run in runs:
		create_run_file(run)

	print("Time taken -", time.time() - start)

if __name__ == '__main__':
	main()
