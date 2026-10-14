import '@fontsource-variable/inter'
import '@fontsource-variable/jetbrains-mono'
import './index.css'
import { MotionConfig } from 'motion/react'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router'
import App from './App'
import { TooltipProvider } from './components/ui/tooltip'
import { initPresentationMode } from './lib/flags'
import { productionServices } from './services/production'
import { ServicesProvider } from './services/services'

initPresentationMode()
document.documentElement.classList.add('dark')

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ServicesProvider services={productionServices()}>
      <MotionConfig reducedMotion="user">
        <TooltipProvider delayDuration={300}>
          <BrowserRouter>
            <App />
          </BrowserRouter>
        </TooltipProvider>
      </MotionConfig>
    </ServicesProvider>
  </StrictMode>,
)
