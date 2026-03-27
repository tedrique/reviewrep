<section class="py-20 px-4">
	<div class="max-w-5xl mx-auto">
		<div class="grid md:grid-cols-3 gap-5">
			{#each [
				{ name: 'James T.', role: 'Restaurant Owner, Bristol', text: 'I used to spend an hour every morning replying to reviews. Now it takes me 5 minutes to approve what the AI wrote. Absolute game changer.' },
				{ name: 'Lisa K.', role: 'Salon Owner, Manchester', text: 'Had a terrible review I was dreading to respond to. The AI nailed it — professional, empathetic, not defensive. Customer actually came back.' },
				{ name: 'Mark R.', role: 'Plumber, Kent', text: 'My Google ranking improved within weeks of starting to reply to every review. At £19 a month it pays for itself ten times over.' }
			] as t, i}
				<div class="scroll-reveal scroll-reveal-delay-{i + 1} bg-white/[0.03] border border-white/5 rounded-2xl p-7 hover:bg-white/[0.05] hover:border-white/10 transition-all duration-300">
					<div class="flex gap-0.5 mb-4">
						{#each Array(5) as _}<span class="text-amber-400 text-sm">&#9733;</span>{/each}
					</div>
					<p class="text-sm text-white/50 leading-relaxed mb-5 italic">"{t.text}"</p>
					<div class="flex items-center gap-3">
						<div class="w-9 h-9 rounded-full bg-gradient-to-br from-blue-400 to-violet-500 flex items-center justify-center text-xs font-bold">{t.name[0]}</div>
						<div>
							<div class="text-sm font-medium">{t.name}</div>
							<div class="text-xs text-white/30">{t.role}</div>
						</div>
					</div>
				</div>
			{/each}
		</div>
	</div>
</section>
