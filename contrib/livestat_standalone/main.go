package main

import (
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"strings"
	"sync"
	"time"
)

type Service struct {
	Id          string    `json:"-"`
	Status      string    `json:"status"`
	LastUpdated time.Time `json:"lastUpdated"`
}

type LiveStats struct {
	Services map[string]*Service

	masterToken  string
	dataFilePath string

	usage sync.RWMutex
}

// Not thread save. Lock `usage` in write mode before calling.
func (ls *LiveStats) save() error {
	if ls.dataFilePath == "" {
		return nil
	}

	file, err := os.OpenFile(ls.dataFilePath, os.O_WRONLY|os.O_CREATE, 0o666)
	if err != nil {
		return err
	}
	defer file.Close()

	return json.NewEncoder(file).Encode(ls)
}

func (ls *LiveStats) saveAndLog() {
	err := ls.save()
	if err != nil {
		fmt.Fprintf(os.Stderr, "save(): %v\n", err)
	}
}

func (ls *LiveStats) load() error {
	if ls.dataFilePath == "" {
		return nil
	}

	file, err := os.Open(ls.dataFilePath)
	if err != nil {
		return err
	}
	defer file.Close()

	return json.NewDecoder(file).Decode(&ls)
}

func stringDefault(a string, b string) string {
	if a == "" {
		return b
	}
	return a
}

const HTML_COMMON_HEADS = `
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=0">
<style>
body { display: flex; justify-content: center; }
table { border-collapse: collapse; }
tr { border: 1px solid black; border-left: none; border-right: none; border-top: none; }
th, td { padding: 0.5em; }
</style>`

func (ls *LiveStats) handlerMain(w http.ResponseWriter, req *http.Request) {
	servicesId := strings.Split(req.FormValue("services"), ",")
	format := stringDefault(req.FormValue("format"), "json")

	ls.usage.RLock()
	defer ls.usage.RUnlock()

	w.Header().Add("Cache-Control", "max-age=300")
	switch format {
	case "json":
		w.Header().Add("Content-Type", "application/json")
		// ... first call to w.Write() below:
		// NOTE: potential memory pressure problem, if clients asks for too many services too quickly, for constructing this map
		res := make(map[string]*Service, len(servicesId))
		for _, id := range servicesId {
			service, exists := ls.Services[id]
			if !exists {
				continue
			}
			res[id] = service
		}
		json.NewEncoder(w).Encode(res)
	case "html":
		w.Header().Add("Content-Type", "text/html")
		// ... first call to w.Write() below:
		fmt.Fprint(w, "<!DOCTYPE html><html><head>", HTML_COMMON_HEADS, "</head><body>")
		fmt.Fprint(w, "<table>", "<tr><th>The thing...</th><th>is...</th><th>since...</th></tr>")
		for _, id := range servicesId {
			service, exists := ls.Services[id]
			if !exists {
				continue
			}
			fmt.Fprintf(w, "<tr><td>%s</td><td>%s</td><td>%s</td></tr>",
				service.Id, service.Status, service.LastUpdated.Local().String())
		}
		fmt.Fprint(w, "</table>")
		fmt.Fprint(w, "</body></html>")
	case "plaintext":
		w.Header().Add("Content-Type", "text/plain")
		// ... first call to w.Write() below:
		for _, id := range servicesId {
			service, exists := ls.Services[id]
			if !exists {
				continue
			}
			fmt.Fprintf(w, "%s\nsince: %s\nis: %s\n\n",
				service.Id,
				service.LastUpdated.Local().Format("2006-01-02 15:04:05 UTC-07"),
				service.Status)
		}
	default:
		http.Error(w, "Invalid format", http.StatusBadRequest)
		return
	}
}

func (ls *LiveStats) handlerNewService(w http.ResponseWriter, req *http.Request) {
	token := req.FormValue("token")
	if token != ls.masterToken {
		http.Error(w, "Invalid token", http.StatusUnauthorized)
		return
	}

	ls.usage.Lock()
	defer ls.usage.Unlock()

	id := req.FormValue("id")
	_, exists := ls.Services[id]
	if exists {
		http.Error(w, "Service already exists", http.StatusConflict)
		return
	}

	ls.Services[id] = &Service{
		Id:          id,
		Status:      "",
		LastUpdated: time.Now(),
	}
	go ls.saveAndLog()
}

func (ls *LiveStats) handlerUpdateStatus(w http.ResponseWriter, req *http.Request) {
	token := req.FormValue("token")
	if token != ls.masterToken {
		http.Error(w, "Invalid token", http.StatusUnauthorized)
		return
	}

	ls.usage.Lock()
	defer ls.usage.Unlock()

	service, exists := ls.Services[req.FormValue("id")]
	if !exists {
		http.Error(w, "Service does not exist", http.StatusBadRequest)
		return
	}

	body, err := io.ReadAll(req.Body)
	if err != nil {
		// This shouldn't happen
		http.Error(w, "", http.StatusInternalServerError)
	}

	service.Status = string(body)
	service.LastUpdated = time.Now()
	go ls.saveAndLog()
}

func (ls *LiveStats) handlerDeleteService(w http.ResponseWriter, req *http.Request) {
	token := req.FormValue("token")
	if token != ls.masterToken {
		http.Error(w, "Invalid token", http.StatusUnauthorized)
		return
	}

	ls.usage.Lock()
	defer ls.usage.Unlock()

	id := req.FormValue("id")
	_, exists := ls.Services[id]
	if !exists {
		http.Error(w, "Service does not exist", http.StatusBadRequest)
		return
	}

	delete(ls.Services, id)
	go ls.saveAndLog()
}

func main() {
	state := LiveStats{
		Services: make(map[string]*Service),

		masterToken:  os.Getenv("MASTER_TOKEN"),
		dataFilePath: os.Getenv("DATA_FILE"),

		usage: sync.RWMutex{},
	}

	err := state.load()
	if err != nil {
		if os.IsNotExist(err) {
			fmt.Printf("load(): DATA_FILE does not exist\n")
		} else {
			fmt.Fprintf(os.Stderr, "load(): %v\n", err)
		}
	} else {
		// Repopulate not-marshaled fields
		for id, service := range state.Services {
			service.Id = id
		}
	}

	http.HandleFunc("GET /", state.handlerMain)
	http.HandleFunc("POST /service", state.handlerNewService)
	http.HandleFunc("POST /service/status", state.handlerUpdateStatus)
	http.HandleFunc("DELETE /service", state.handlerDeleteService)
	http.ListenAndServe(stringDefault(os.Getenv("LISTEN"), ":38083"), nil)
}
