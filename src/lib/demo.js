import { createContext, useContext } from 'react'

// Lets any component open the "Book a demo" dialog
export const DemoContext = createContext(() => {})
export const useOpenDemo = () => useContext(DemoContext)
