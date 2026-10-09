import axios from 'axios'

export const API_BASE = import.meta.env.VITE_API_BASE || '/api/v1'

const apiClient = axios.create({
  baseURL: API_BASE,
  timeout: 120000,
  headers: { 'Content-Type': 'application/json' },
})

apiClient.interceptors.request.use(config => config, error => Promise.reject(error))
apiClient.interceptors.response.use(
  response => response.data,
  error => {
    const message = error.response?.data?.detail || error.message
    return Promise.reject(new Error(message))
  }
)

export default apiClient
