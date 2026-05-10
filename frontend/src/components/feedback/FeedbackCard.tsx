import { Badge } from "@/components/ui/badge"
import { Card, CardContent } from "@/components/ui/card"
import type { Feedback, Sentiment } from "@/lib/api/types"
import { feedback as feedbackCopy } from "@/locales/en/feedback"

const sentimentVariant: Record<
  Sentiment,
  "default" | "secondary" | "destructive"
> = {
  positive: "default",
  neutral: "secondary",
  negative: "destructive",
}

const sentimentLabel: Record<Sentiment, string> = {
  positive: feedbackCopy.sentiment.positive,
  neutral: feedbackCopy.sentiment.neutral,
  negative: feedbackCopy.sentiment.negative,
}

interface FeedbackCardProps {
  feedback: Feedback
}

export function FeedbackCard({ feedback }: FeedbackCardProps) {
  return (
    <Card>
      <CardContent className="flex flex-col gap-3 pt-6">
        <p className="text-sm text-foreground">{feedback.text}</p>

        {feedback.status === "extracted" && feedback.sentiment && (
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs text-muted-foreground">
              {feedbackCopy.card.sentimentLabel}:
            </span>
            <Badge variant={sentimentVariant[feedback.sentiment]}>
              {sentimentLabel[feedback.sentiment]}
            </Badge>
            {feedback.language && (
              <Badge variant="outline" className="ml-auto text-xs">
                {feedback.language}
              </Badge>
            )}
          </div>
        )}

        {feedback.themes.length > 0 && (
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs text-muted-foreground">
              {feedbackCopy.card.themesLabel}:
            </span>
            {feedback.themes.map((theme) => (
              <Badge key={theme} variant="outline">
                {theme}
              </Badge>
            ))}
          </div>
        )}

        {feedback.action_items.length > 0 && (
          <div className="flex flex-col gap-1">
            <span className="text-xs text-muted-foreground">
              {feedbackCopy.card.actionItemsLabel}:
            </span>
            <ul className="list-disc list-inside text-sm">
              {feedback.action_items.map((item, i) => (
                <li key={i}>{item}</li>
              ))}
            </ul>
          </div>
        )}

        {feedback.status === "skipped" && feedback.skip_reason && (
          <div className="flex items-center gap-2">
            <Badge variant="secondary">{feedbackCopy.card.skippedLabel}</Badge>
            <span className="text-xs text-muted-foreground">
              {feedbackCopy.card.skipReasonLabel}: {feedback.skip_reason}
            </span>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
