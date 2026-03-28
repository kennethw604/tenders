import Anthropic from "@anthropic-ai/sdk";
import { Database } from "../database.types";

type Tender = Database["public"]["Tables"]["tenders"]["Row"];
type TenderSummaries = {
  id: string;
  summary: string | null;
}[];

export class AiService {
  private anthropic: Anthropic;
  private model: string;

  // Chat sessions storage (in-memory for now)
  private chatSessions = new Map<string, { role: string; content: string }[]>();

  constructor() {
    this.anthropic = new Anthropic({
      apiKey: process.env.ANTHROPIC_API_KEY,
    });
    this.model = process.env.ANTHROPIC_MODEL || "claude-sonnet-4-20250514";
  }

  async generateLeads(prompt: string) {
    const response = await this.anthropic.messages.create({
      model: this.model,
      max_tokens: 1024,
      system: "You are a helpful assistant.",
      messages: [{ role: "user", content: prompt }],
    });
    return response.content[0].type === "text" ? response.content[0].text : "";
  }

  async analyzeRfp(rfpData: any) {
    const response = await this.anthropic.messages.create({
      model: this.model,
      max_tokens: 1024,
      system: "You are an AI that summarizes data",
      messages: [{ role: "user", content: JSON.stringify(rfpData) }],
    });
    return response.content[0].type === "text" ? response.content[0].text : "";
  }

  async filterTendersBySummary(tenders: TenderSummaries, query: string) {
    console.log("tenders", tenders);
    console.log("query", query);
    const tendersToAnalyze = tenders
      .map((tender) => {
        return `id: ${tender.id} + summary: ${tender.summary}`;
      })
      .join("\n");

    try {
      const response = await this.anthropic.messages.create({
        model: this.model,
        max_tokens: 1024,
        system: `You are an expert in government tenders. Your task is to find which tenders match the given query based on their summaries. Return only a JSON array of IDs.`,
        messages: [
          {
            role: "user",
            content: `You are a helpful assistant tasked with filtering government tenders based on a user query.

Given a list of tenders in the format:
id: <ID> + summary: <SUMMARY>

Return a JSON array of IDs that match the following query:
"${query}"

Tenders:
${tendersToAnalyze}

Return only a valid JSON array of IDs, like ["abc123", "def456"].`,
          },
        ],
      });
      const text =
        response.content[0].type === "text" ? response.content[0].text : "[]";
      console.log("response", text);
      return JSON.parse(text);
    } catch (error) {
      console.error("Error filtering tenders:", error);
      throw new Error("Failed to filter tenders");
    }
  }

  async filterTenders(prompt: string, tenderData: any[]) {
    const response = await this.anthropic.messages.create({
      model: this.model,
      max_tokens: 1024,
      system: `You are an AI that helps users filter a database of government tenders.
You MUST return a valid JSON response matching this exact format:
{
  "matches": ["REF1", "REF2"]
}

You are provided with tender objects containing:
- 'referenceNumber-numeroReference' (the ID)
- 'tenderDescription-descriptionAppelOffres-eng' (the description)

Your task:
1. Read each tender description
2. Find matches for this request: "${prompt}"
3. Return ONLY valid JSON with matching reference IDs

The tender data to analyze is:`,
      messages: [{ role: "user", content: JSON.stringify(tenderData) }],
    });
    return response.content[0].type === "text"
      ? response.content[0].text
      : "{}";
  }

  async generatePrecomputedSummary(tender: Tender): Promise<string> {
    try {
      const keyInfo = {
        title: tender.title,
        description: tender.description,
        category: tender.category_primary,
        entity: tender.contracting_entity_name,
        closing_date: tender.closing_date,
        regions: tender.delivery_location,
      };

      const prompt = `Summarize this government tender in 3 sentences focusing on the MOST important information for businesses:

Title: ${keyInfo.title}
Description: ${keyInfo.description}
Category: ${keyInfo.category}
Entity: ${keyInfo.entity}
Closing Date: ${keyInfo.closing_date}
Regions: ${keyInfo.regions}

Return ONLY the summary text, no JSON, no formatting. Focus on what they're buying, from which organization, and key constraints like deadline or location.`;

      const response = await this.anthropic.messages.create({
        model: this.model,
        max_tokens: 300,
        system:
          "You are an expert at creating concise, business-focused summaries of government tenders. Your summaries help businesses quickly understand opportunities. Be direct and factual.",
        messages: [{ role: "user", content: prompt }],
      });
      const text =
        response.content[0].type === "text" ? response.content[0].text : "";
      console.log("Precomputed summary:", text);
      return text.trim() || "No summary available";
    } catch (error) {
      console.error("Error generating precomputed summary:", error);
      return "Summary generation failed";
    }
  }

  async generateTenderSummary(tenderId: string, tenderData: string) {
    try {
      const response = await this.anthropic.messages.create({
        model: this.model,
        max_tokens: 300,
        system: `You are BreezeAI, an expert AI assistant specialized in analyzing government procurement tenders. Create a concise, business-focused summary that helps companies quickly understand if this opportunity is worth pursuing.

You MUST respond with valid JSON matching this schema:
{
  "summary": "2-3 sentence executive summary of the opportunity",
  "keyDetails": {
    "objective": "What they're buying/seeking",
    "category": "Procurement category",
    "value": "Estimated value or budget range"
  },
  "requirements": ["Top 3-5 key requirements"],
  "recommendation": {
    "priority": "High, Medium, Low, or Skip",
    "reason": "Brief reason for the recommendation"
  }
}`,
        messages: [
          {
            role: "user",
            content: `Analyze this government tender data and provide a concise, actionable summary: ${tenderData}`,
          },
        ],
      });

      const text =
        response.content[0].type === "text" ? response.content[0].text : "{}";
      return { summary: text };
    } catch (error) {
      console.error("Error generating tender summary:", error);
      throw new Error("Failed to generate tender summary");
    }
  }

  async createChatSession(sessionId: string) {
    const history = [
      {
        role: "user",
        content:
          "Hello! I'm looking for help with government tenders and procurement opportunities.",
      },
      {
        role: "assistant",
        content:
          "Hello! I'm here to help you with government tenders and procurement opportunities. I can answer questions about tender processes, requirements, deadlines, and help you understand specific opportunities. What would you like to know?",
      },
    ];

    this.chatSessions.set(sessionId, history);
    return history;
  }

  async sendChatMessage(sessionId: string, message: string) {
    try {
      let history = this.chatSessions.get(sessionId);

      if (!history) {
        history = (await this.createChatSession(sessionId)) as {
          role: string;
          content: string;
        }[];
      }

      history.push({ role: "user", content: message });

      const response = await this.anthropic.messages.create({
        model: this.model,
        max_tokens: 1024,
        system:
          "You are a helpful AI assistant specialized in government tenders and procurement opportunities.",
        messages: history as any,
      });

      const assistantMessage =
        response.content[0].type === "text" ? response.content[0].text : "";
      history.push({ role: "assistant", content: assistantMessage });

      this.chatSessions.set(sessionId, history);

      return {
        message: assistantMessage,
        sessionId: sessionId,
      };
    } catch (error) {
      console.error("Error sending chat message:", error);
      throw new Error("Failed to send chat message");
    }
  }

  getChatSession(sessionId: string) {
    return this.chatSessions.get(sessionId);
  }

  deleteChatSession(sessionId: string) {
    return this.chatSessions.delete(sessionId);
  }
}
