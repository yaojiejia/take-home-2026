import { StrictMode } from "react"
import { createRoot } from "react-dom/client"
import { BrowserRouter, Route, Routes } from "react-router-dom"
import "./index.css"
import { Layout } from "@/components/Layout"
import { CatalogPage } from "@/pages/CatalogPage"
import { ProductPage } from "@/pages/ProductPage"

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<CatalogPage />} />
          <Route path="/products/:id" element={<ProductPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  </StrictMode>,
)
