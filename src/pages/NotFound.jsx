import { useEffect } from 'react'
import { setPageMeta } from '../lib/router'

export default function NotFound() {
  useEffect(() => {
    setPageMeta('Page not found | DEVLIQLY')
  }, [])

  return (
    <main className="notfound">
      <div className="container">
        <p className="label">( 404 )</p>
        <h1 className="notfound__title">Lost the <em>signal</em></h1>
        <p className="lead">The page you&apos;re looking for doesn&apos;t exist or has moved.</p>
        <a href="/" className="btn">Back to home</a>
      </div>
    </main>
  )
}
