// Daniel Locke, 2017
package main 

import (
    "encoding/json"
    "flag"
	"fmt"
	"io/ioutil"
	"log"
	"os"
	"regexp"
	"strings"
	"strconv"
	"time"

	html "github.com/jaytaylor/html2text"
)

type Opinion struct {
	ResourceUri string `json:"resource_uri"`
	AbsoluteUrl string `json:"absolute_url"`
	PlainText string `json:"plain_text"`
	Html string `json:"html_with_citations"`
	Cited []string `json:"opinions_cited"`
	Cluster string `json:"cluster"`
}

type Cluster struct {
	OpinionId int `json:""`
	DateFiled string `json:"date_filed"`
	CaseName string `json:"case_name"`
}

type Doc struct {
	Id int `json:"id"`
	Cluster int `json:"cluster"`
	OpinionResourceUri string `json:"opinion_resource_uri"`
	OpinionAbsoluteUrl string `json:"opinion_absolute_url"`
	DateFiled string `json:"date_filed"`
	Title string `json:"title"`
	PlainText string `json:"plain_text"`
	Html string `json:"html_with_citations"`
	Cited []int `json:"cited"`
}

func generateFolderFileList(folder string) []string {
	temp := make([]string, 0)
	fileInfo, err := ioutil.ReadDir(folder)
	if err != nil {
		log.Panic(err)
	}
	for _, i := range fileInfo {
		temp = append(temp, i.Name())
	}
	return temp
}

func OpenJsonFile(filepath string) (*os.File, error) {
	return os.OpenFile(filepath, os.O_RDWR, 0755)
}
	
func GenerateDocs(op_path, clust_path, docs_path string) {
	opinions := generateFolderFileList(op_path)

	for _, j := range opinions { 
		if strings.HasPrefix(j, ".") {
			continue 
		}
		doc := Doc{}
		op_file, err := OpenJsonFile(op_path + j)
		if err != nil {
			log.Panic(err)
		}
		op := Opinion{}
		json.NewDecoder(op_file).Decode(&op)

		doc.Id, err = strconv.Atoi(strings.Replace(j, ".json","", -1))
		if err != nil {
			log.Panic(err)
		}
		doc.OpinionResourceUri = op.ResourceUri
		doc.OpinionAbsoluteUrl = op.AbsoluteUrl

		stripped, err := html.FromString(op.Html, html.Options{PrettyTables: false})
		if err != nil {
			log.Panic(err)
		}

		// regex to strip chars... 
		re := regexp.MustCompile(`[^a-zA-Z0-9.]+`)
		doc.PlainText = re.ReplaceAllString(stripped, " ")

		doc.Html = op.Html

		for _, citation := range op.Cited {
			cit := strings.Replace(citation, "http://www.courtlistener.com/api/rest/v3/opinions/", "", 1)
			cit = strings.Replace(cit, "/", "", 1)
			c, err := strconv.Atoi(cit)
			if err != nil {
				log.Panic(err)
			}
			doc.Cited = append(doc.Cited, c)
		} 
		op_file.Close()
		cluster := strings.Replace(op.Cluster, "http://www.courtlistener.com/api/rest/v3/clusters/", "", 1)
		cluster = strings.Replace(cluster, "/", "", 1)
		doc.Cluster, err = strconv.Atoi(cluster)
		if err != nil {
			log.Panic(err)
		}
		clust_file_name := cluster + ".json"
		clust_file, err := OpenJsonFile(clust_path + clust_file_name)
		if err != nil {
			log.Panic(err)
		}

		c := Cluster{}
		json.NewDecoder(clust_file).Decode(&c)

		doc.Title = c.CaseName
		doc.DateFiled = c.DateFiled

		tmp, err := json.MarshalIndent(doc, "", "     ")
		if err != nil {
			log.Panic(err)
		}
		doc_file_name := docs_path + j
		doc_file, err := os.OpenFile(doc_file_name, os.O_CREATE|os.O_RDWR, 0755)
		if err != nil {
			log.Panic(err)
		}
		doc_file.Write(tmp)
		doc_file.Close()
		clust_file.Close()
	}
}

func main() {
	start := time.Now()
	fmt.Println(`

====================================
USSC collection -
As part of AIRS submission -
Locke, Zuccon and Scells, 'Automatic Query Generation from Legal Texts for Case Law Retrieval'
	`)
	opsPtr := flag.String("op", "", "Path to doc folder.")
	clustPtr := flag.String("c", "", "Path to cluster folder.")
	docsPtr := flag.String("out", "", "Output path.")
	flag.Parse()
	if *opsPtr == "" || *clustPtr == "" || *docsPtr == "" {
		fmt.Println("Missing input path.")
		return
	}  
	GenerateDocs(*opsPtr, *clustPtr, *docsPtr)
	
	fmt.Println("Completed in", time.Since(start))
}