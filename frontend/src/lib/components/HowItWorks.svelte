<section class="py-20 md:py-28 px-4">
	<div class="max-w-4xl mx-auto">
		<div class="scroll-reveal text-center mb-16">
			<h2 class="text-2xl md:text-4xl font-bold mb-3">How it works</h2>
			<p class="text-white/40">Three steps. Two minutes setup. Done.</p>
		</div>

		<div class="relative">
			<!-- Connection line -->
			<div class="hidden md:block absolute top-16 left-[16.5%] right-[16.5%] h-px bg-gradient-to-r from-blue-500/30 via-violet-500/30 to-emerald-500/30"></div>

			<div class="grid md:grid-cols-3 gap-8 md:gap-12">
				{#each [
					{ num: '1', title: 'Connect Google', desc: 'One click to connect your Google Business Profile. We pull in your reviews automatically.', gradient: 'from-blue-500 to-blue-600', glow: 'shadow-blue-500/20' },
					{ num: '2', title: 'AI writes the reply', desc: 'In your brand\'s voice. Professional for negative reviews, warm for positive. Always sounds human.', gradient: 'from-violet-500 to-violet-600', glow: 'shadow-violet-500/20' },
					{ num: '3', title: 'You approve', desc: 'One click to publish. Or edit first. Either way — done in 10 seconds, not 10 minutes.', gradient: 'from-emerald-500 to-emerald-600', glow: 'shadow-emerald-500/20' }
				] as step, i}
					<div class="scroll-reveal scroll-reveal-delay-{i + 1} text-center">
						<div class="w-14 h-14 rounded-2xl bg-gradient-to-br {step.gradient} flex items-center justify-center text-xl font-bold mx-auto mb-5 shadow-lg {step.glow}">{step.num}</div>
						<h3 class="font-bold text-lg mb-2">{step.title}</h3>
						<p class="text-sm text-white/40 leading-relaxed">{step.desc}</p>
					</div>
				{/each}
			</div>
		</div>
	</div>
</section>
