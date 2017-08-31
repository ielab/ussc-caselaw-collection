import os 
import subprocess

qrel_path = "../../ussc-collection/airs2017-collection/qrel.txt"


trec_path = "../../ussc-queries/trec_eval.9.0"
trec_eval_output_path = "../../ussc-collection/airs2017-experiments/results/res-files/"


def trec_eval_to_csv(out_file_name, process_args, eval_output):
	os.chdir(trec_path)

	res_file_name = trec_eval_output_path + out_file_name + ".csv"
	res_file = open(res_file_name, 'w+')

	header_row = "q-num"
	for i in eval_output:
		header_row += ", " + i
	header_row += "\n"
	res_file.write(header_row)

	res = subprocess.Popen(process_args, stdout=subprocess.PIPE)

	num_param = len(eval_output)
	evals = [""] * num_param
	query = ""

	for line in res.stdout:
		line = line.decode('ascii')
		if num_param > 1:
			if query == "": 
				query = line.split()[1]

			if query == line.split()[1]:
				for i in range(num_param):
					measure = line.split()[0]
					if measure == eval_output[i]:
						evals[i] = line.split()[2]

			else:
				# write old data
				l = query
				for i in range(num_param):
					l  += "," + evals[i]
				l += "\n"
				res_file.write(l)
				
				if line.split()[1] == "all": 
					break 
				
				# get new data
				else:
					query = line.split()[1]
					evals = [""] * num_param
					for i in range(num_param):
						measure = line.split()[0]
						if measure == eval_output[i]:
							evals[i] = line.split()[2]
		
		else: 
			query = line.split()[1]
			score = line.split()[2]
			if query != "all":
				l = query + "," + score + "\n" 
				res_file.write(l)

	res_file.close()


def main():
	file_end = "_res_file.txt"
	file_path = "../../ussc-collection/airs2017-experiments/run-files/"

	runs = ["adhocbool1", "adhocbool2", "adhocbool3", "adhocsim1", "adhocsim2", "adhocsim3", "topsen", "toppar", "adhockey"]
	base = ["idfs", "idfp", "plms", "plmp", "klis", "klip"]
	
	for run in base:
		for i in range(1, 12):
			if "plm" in run:
				for j in range(1, 11):
					runs.append(run + str(i) + "_" + str(j))
			else:
				runs.append(run + str(i))

	run_file = []
	for run in runs:
		run_file.append((file_path + run + file_end, run))
	for file in run_file:
		trec_eval_to_csv( file[1] + "_standard", 
			['./trec_eval', '-q', '-m', 'P.1,5', '-m', 'map', '-M', '5', qrel_path, file[0]], 
			["P_1", "P_5", "map"])
		trec_eval_to_csv( file[1] + "_recip", 
			['./trec_eval', '-q', '-m', 'recip_rank', qrel_path, file[0]], 
			["recip_rank"])


if __name__ == '__main__':
	main()
