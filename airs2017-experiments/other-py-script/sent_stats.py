
import json

topic_path = "../airs2017-collection/topic/"

def topic_stats():
	av_sent_len = 0
	av_para_len = 0

	for topic in range(1, 101):
		topic_case_id = 0
		skip_write = False
		topic_file_name = topic_path + str(topic) + ".json"
		with open(topic_file_name) as topic_file:
			topic_data = json.load(topic_file)

			av_sent_len += len(topic_data['citing_sentence'].split(' '))
			av_para_len += len(topic_data['citing_paragraph'].split(' '))

	av_sent_len = av_sent_len / 100
	av_para_len = av_para_len / 100

	print("Av sent len -", av_sent_len)
	print("Av para len -", av_para_len)

def main():
	topic_stats()

if __name__ == '__main__':
	main()
