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

// Initialize in main() and NEVER changed again
var masterToken string

type Service struct {
	id string

	status string

	lastUpdated time.Time
}

type LiveStats struct {
	services map[string]*Service

	usage sync.RWMutex
}

func (ls *LiveStats) save() {

}

func stringDefault(a string, b string) string {
	if a == "" {
		return b
	}
	return a
}

const HTML_STYLES = `
<style>
table { border-collapse: collapse; }
th, td { border: 1px solid black; padding: 0.5em; }
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
			service, exists := ls.services[id]
			if !exists {
				continue
			}
			res[id] = service
		}
		json.NewEncoder(w).Encode(res)
	case "html":
		w.Header().Add("Content-Type", "text/html")
		// ... first call to w.Write() below:
		fmt.Fprint(w, "<html><head>", HTML_STYLES, "</head><body>")
		fmt.Fprint(w, "<table>", "<tr><th>Service</th><th>Status</th><th>Last Updated</th></tr>")
		for _, id := range servicesId {
			service, exists := ls.services[id]
			if !exists {
				continue
			}
			fmt.Fprintf(w, "<tr><td>%s</td><td>%s</td><td>%s</td></tr>",
				service.id, service.status, service.lastUpdated.Local().String())
		}
		fmt.Fprint(w, "</table>")
		fmt.Fprint(w, "</body></html>")
	case "plaintext":
		w.Header().Add("Content-Type", "text/plain")
		// ... first call to w.Write() below:
		for _, id := range servicesId {
			service, exists := ls.services[id]
			if !exists {
				continue
			}
			fmt.Fprintf(w, `%s
since: %s
is: %s\n`,
				service.id, service.lastUpdated.Local().String(), service.status)
		}
	default:
		http.Error(w, "Invalid format", http.StatusBadRequest)
		return
	}
}

func (ls *LiveStats) handlerNewService(w http.ResponseWriter, req *http.Request) {
	token := req.FormValue("token")
	if token != masterToken {
		http.Error(w, "Invalid token", http.StatusUnauthorized)
		return
	}

	ls.usage.Lock()
	defer ls.usage.Unlock()

	id := req.FormValue("id")
	_, exists := ls.services[id]
	if exists {
		http.Error(w, "Service already exists", http.StatusConflict)
		return
	}

	ls.services[id] = &Service{
		id:          id,
		status:      "",
		lastUpdated: time.Now(),
	}
}

func (ls *LiveStats) handlerUpdateStatus(w http.ResponseWriter, req *http.Request) {
	token := req.FormValue("token")
	if token != masterToken {
		http.Error(w, "Invalid token", http.StatusUnauthorized)
		return
	}

	ls.usage.Lock()
	defer ls.usage.Unlock()

	service, exists := ls.services[req.FormValue("id")]
	if !exists {
		http.Error(w, "Service does not exist", http.StatusBadRequest)
		return
	}

	body, err := io.ReadAll(req.Body)
	if err != nil {
		// This shouldn't happen
		http.Error(w, "", http.StatusInternalServerError)
	}

	service.status = string(body)
	service.lastUpdated = time.Now()
}

func (ls *LiveStats) handlerDeleteService(w http.ResponseWriter, req *http.Request) {
	token := req.FormValue("token")
	if token != masterToken {
		http.Error(w, "Invalid token", http.StatusUnauthorized)
		return
	}

	ls.usage.Lock()
	defer ls.usage.Unlock()

	id := req.FormValue("id")
	_, exists := ls.services[id]
	if !exists {
		http.Error(w, "Service does not exist", http.StatusBadRequest)
		return
	}

	delete(ls.services, id)
}

func main() {
	masterToken = os.Getenv("MASTER_TOKEN")

	state := LiveStats{
		services: make(map[string]*Service),

		usage: sync.RWMutex{},
	}

	http.HandleFunc("GET /", state.handlerMain)
	http.HandleFunc("POST /service", state.handlerNewService)
	http.HandleFunc("POST /service/status", state.handlerUpdateStatus)
	http.HandleFunc("DELETE /service", state.handlerDeleteService)
	http.ListenAndServe(":38083", nil)
}
