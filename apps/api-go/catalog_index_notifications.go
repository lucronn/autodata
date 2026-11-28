package main

import (
	"context"
	"sync"
	"time"

	"github.com/jackc/pgx/v5"
)

const catalogIndexWaitPreference = "workshop-index-wait-for-first-rows"
const catalogIndexWaitDuration = 1450 * time.Millisecond

type catalogIndexSubscription struct {
	changed chan struct{}
	readers int
}

// One connection listens for committed changes. HTTP waiters hold no database
// transaction or pool connection and can only watch their already authorized scope.
type catalogIndexNotifications struct {
	mu          sync.Mutex
	online      bool
	subscribers map[string]*catalogIndexSubscription
}

func listenCatalogIndexChanges(ctx context.Context, config *pgx.ConnConfig) *catalogIndexNotifications {
	changes := &catalogIndexNotifications{subscribers: make(map[string]*catalogIndexSubscription)}
	go func() {
		for ctx.Err() == nil {
			changes.listen(ctx, config)
			select {
			case <-ctx.Done():
				return
			case <-time.After(time.Second):
			}
		}
	}()
	return changes
}

func (n *catalogIndexNotifications) listen(ctx context.Context, config *pgx.ConnConfig) {
	connectCtx, cancel := context.WithTimeout(ctx, 3*time.Second)
	defer cancel()
	conn, err := pgx.ConnectConfig(connectCtx, config)
	if err != nil {
		return
	}
	defer func() {
		closeCtx, cancel := context.WithTimeout(context.Background(), time.Second)
		defer cancel()
		_ = conn.Close(closeCtx)
	}()
	if _, err := conn.Exec(connectCtx, "LISTEN autodata_workshop_index"); err != nil {
		return
	}
	n.mu.Lock()
	n.online = true
	n.mu.Unlock()
	defer func() {
		n.mu.Lock()
		defer n.mu.Unlock()
		n.online = false
		for id, sub := range n.subscribers {
			delete(n.subscribers, id)
			close(sub.changed)
		}
	}()
	for {
		event, err := conn.WaitForNotification(ctx)
		if err != nil {
			return
		}
		n.mu.Lock()
		if sub := n.subscribers[event.Payload]; sub != nil {
			delete(n.subscribers, event.Payload)
			close(sub.changed)
		}
		n.mu.Unlock()
	}
}

func (n *catalogIndexNotifications) watch(id string) (<-chan struct{}, func()) {
	n.mu.Lock()
	defer n.mu.Unlock()
	if !n.online {
		return nil, nil
	}
	sub := n.subscribers[id]
	if sub == nil {
		sub = &catalogIndexSubscription{changed: make(chan struct{})}
		n.subscribers[id] = sub
	}
	sub.readers++
	return sub.changed, func() {
		n.mu.Lock()
		defer n.mu.Unlock()
		if n.subscribers[id] == sub {
			sub.readers--
			if sub.readers == 0 {
				delete(n.subscribers, id)
			}
		}
	}
}

func (n *catalogIndexNotifications) available() bool {
	n.mu.Lock()
	defer n.mu.Unlock()
	return n.online
}
