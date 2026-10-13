import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App'
import { initAppCheck } from './firebase'

initAppCheck()
createRoot(document.getElementById('root')!).render(<StrictMode><App /></StrictMode>)
