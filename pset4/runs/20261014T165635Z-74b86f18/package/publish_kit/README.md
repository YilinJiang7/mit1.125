# Publishing kit for run 2

As-of date: **2026-10-14**. This kit is derived only from the approved package’s articles, scripts and source notes. Approved artifacts and approval remain unchanged. No collection, generation, re-review, approval or package command was rerun while creating this kit.

## Files

| Piece | Substack page | YouTube title/description | Google Vids / HeyGen sheet |
| --- | --- | --- | --- |
| 01 | [substack_01.html](substack_01.html) | [youtube_01.txt](youtube_01.txt) | [vids_01.md](vids_01.md) |
| 02 | [substack_02.html](substack_02.html) | [youtube_02.txt](youtube_02.txt) | [vids_02.md](vids_02.md) |
| 03 | [substack_03.html](substack_03.html) | [youtube_03.txt](youtube_03.txt) | [vids_03.md](vids_03.md) |

## Manual order — repeat for each piece, then confirm the package

1. **Publish the article on Substack.** Open its standalone HTML page in a browser, use **Cmd+A → Cmd+C**, and paste the rich text into the Substack editor. Use the first line as the title and the second line as the subtitle, moving them into dedicated fields if the editor requires it. Set access to **free, no paywall, no paid subscription requirement**. Check that the numbered citation links and disclosure survive the paste. Publish and save the article URL; `VIDEO_LINK` is replaced in step 3.
2. **Upload the video to YouTube as Unlisted with its description.** First use the matching production sheet in Google Vids or HeyGen: paste “Help me create,” then paste the single full-narration block as the voiceover. Follow its scenes and source credits, review voice/visuals, and export the video. Upload with visibility **Unlisted**. The first line of `youtube_0N.txt` is the title; everything after `Description:` is the description. Paste the numbered sources and disclosure too. Save the YouTube URL; `ARTICLE_LINK` is replaced in step 3. Keep the voice/visual disclosure consistent with the tool actually used.
3. **Replace `VIDEO_LINK` / `ARTICLE_LINK` in both published places.** Edit the Substack “Watch the video” link to use the unlisted YouTube URL. Edit the YouTube description’s “Read the full article” link to use the published Substack URL. Replace the corresponding placeholders in the local HTML/TXT kit files too; leave approved package articles/scripts, briefs and approval unchanged. Check both published links.
4. **Fill `package/publication_links.json`.** In the [existing link file](../publication_links.json), replace each piece’s `substack_url` and `youtube_url` nulls with its real published URLs, retaining all three piece records. Verify course staff can open the free article and unlisted video.
5. **Re-run packaging and confirm entered links are preserved.** From the `pset4` repository root:

   ```bash
   bash run.sh --package runs/20261014T165635Z-74b86f18
   ```

   Compare `package/publication_links.json` before and after; the entered URLs must remain identical. Packaging is a verification/handoff step and does not itself publish anything.

## Conversion and verification

Article prose comes from the approved package, with Markdown converted to HTML. Numbered superscript citations point directly to the packaged source URLs, not local files. Repeated written passages from one URL share a number; distinct media timestamps retain distinct numbers. YouTube URLs preserve their `&t=` seconds. Podcast citations show `mm:ss` in the link text and use the packaged episode URL. A stray, non-source limitation label in article 03 is omitted from the rendered HTML only. Every AI-assistance/editor disclosure is retained. No new factual claims are added.

Narration is extracted in approved scene order, with only inline-code backticks removed for plain-text pasting. All narration words and punctuation are preserved; on-screen directions and source notes are outside the voiceover block. Numbered bullets in the approved second script are retained as plain text.

| Piece | Approved narration words | Kit narration words | Scenes | YouTube title characters | Numbered sources |
| --- | ---: | ---: | ---: | ---: | ---: |
| 01 | 518 | 518 | 5 | 87 | 6 |
| 02 | 670 | 670 | 10 | 82 | 5 |
| 03 | 635 | 635 | 8 | 97 | 10 |

Verification checks citation numbers against the package’s source notes, validates YouTube timestamp parameters and podcast labels, checks title and scene-text limits, compares narration words with the approved scripts, checks for leaked internal identifiers, and hashes every pre-existing tracked artifact to prove it stayed unchanged. Source URL checks establish the exact packaged targets; they do not assert that external platforms will remain available. No model/API calls are needed to prepare this kit.

The agent browser tool blocked the local-file preview because its URL policy permits only HTTP/HTTPS. HTML structure and rendered-text equivalence were validated mechanically; visual rendering and the Substack paste should be checked manually in your browser/editor.
