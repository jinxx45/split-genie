import { BrowserRouter, Route, Routes } from 'react-router'
import { Privacy, Terms } from './pages/Legal'
import { NewSplit } from './pages/NewSplit'
import { SplitPage } from './pages/SplitPage'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<NewSplit />} />
        <Route path="/split/:id" element={<SplitPage />} />
        <Route path="/privacy" element={<Privacy />} />
        <Route path="/terms" element={<Terms />} />
      </Routes>
    </BrowserRouter>
  )
}
