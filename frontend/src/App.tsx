import { BrowserRouter, Route, Routes } from 'react-router'
import { NewSplit } from './pages/NewSplit'
import { SplitPage } from './pages/SplitPage'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<NewSplit />} />
        <Route path="/split/:id" element={<SplitPage />} />
      </Routes>
    </BrowserRouter>
  )
}
