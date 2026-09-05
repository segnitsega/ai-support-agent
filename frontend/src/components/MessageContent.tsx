import ReactMarkdown from 'react-markdown'
import remarkBreaks from 'remark-breaks'

type Props = {
  text: string
  streaming?: boolean
  plain?: boolean
}

export function MessageContent({ text, streaming, plain }: Props) {
  if (!text) {
    return <>{streaming ? '…' : ''}</>
  }

  if (plain) {
    return <>{text}</>
  }

  return (
    <div className="md">
      <ReactMarkdown
        remarkPlugins={[remarkBreaks]}
        components={{
          a: ({ href, children }) => (
            <a href={href} target="_blank" rel="noreferrer noopener">
              {children}
            </a>
          ),
        }}
      >
        {text}
      </ReactMarkdown>
    </div>
  )
}
