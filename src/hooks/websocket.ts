import { defineStore } from 'hooks/store'
import { useToast } from 'hooks/toast'
import { ref } from 'vue'

type MessageHandler = (message: any) => void

export const useWebSocket = defineStore('websocket', () => {
  const { toast } = useToast()
  const connected = ref(false)
  const messageHandlers = ref<MessageHandler[]>([])
  let ws: WebSocket | null = null
  let reconnectTimeout: NodeJS.Timeout | null = null

  const connect = () => {
    if (ws) {
      return
    }

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsUrl = `${protocol}//${window.location.host}/model-manager/ws`

    ws = new WebSocket(wsUrl)

    ws.onopen = () => {
      connected.value = true
      if (reconnectTimeout) {
        clearTimeout(reconnectTimeout)
        reconnectTimeout = null
      }
    }

    ws.onclose = () => {
      connected.value = false
      ws = null

      // Try to reconnect after 5 seconds
      if (!reconnectTimeout) {
        reconnectTimeout = setTimeout(() => {
          reconnectTimeout = null
          connect()
        }, 5000)
      }
    }

    ws.onerror = (error) => {
      console.error('WebSocket error:', error)
      toast.add({
        severity: 'error',
        summary: 'WebSocket Error',
        detail: 'Failed to connect to server',
        life: 5000,
      })
    }

    ws.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data)
        messageHandlers.value.forEach((handler) => {
          try {
            handler(message)
          } catch (e) {
            console.error('Error in message handler:', e)
          }
        })
      } catch (e) {
        console.error('Error parsing WebSocket message:', e)
      }
    }
  }

  const disconnect = () => {
    if (ws) {
      ws.close()
      ws = null
    }
    if (reconnectTimeout) {
      clearTimeout(reconnectTimeout)
      reconnectTimeout = null
    }
    connected.value = false
  }

  const send = (message: any) => {
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      console.warn('WebSocket not connected')
      return
    }
    ws.send(JSON.stringify(message))
  }

  const onMessage = (handler: MessageHandler) => {
    messageHandlers.value.push(handler)
    return () => {
      const index = messageHandlers.value.indexOf(handler)
      if (index !== -1) {
        messageHandlers.value.splice(index, 1)
      }
    }
  }

  // Connect on creation
  connect()

  return {
    connected,
    connect,
    disconnect,
    send,
    onMessage,
  }
}) 