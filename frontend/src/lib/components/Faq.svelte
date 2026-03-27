<script lang="ts">
	let openIndex = $state(-1);

	const faqs = [
		{ q: 'Does responding to reviews really help?', a: 'Yes. Google confirms that responding to reviews improves your local search ranking. 89% of consumers read business responses before choosing where to go.' },
		{ q: 'Will the replies sound like a robot?', a: 'No. We use advanced AI that writes in natural British English, tailored to your business tone. Every reply is unique and addresses what the customer actually said.' },
		{ q: 'Can I edit replies before publishing?', a: 'Absolutely. You always have full control. Edit any reply or approve it as-is with one click. Nothing gets published without your approval.' },
		{ q: 'What happens after my free trial?', a: 'After 7 days, choose a plan to continue. Your data and settings are preserved. If you don\'t subscribe, your account stays but AI generation pauses.' },
		{ q: 'Can I cancel anytime?', a: 'Yes. Cancel from your dashboard. No contracts, no hidden fees, no questions asked. Cancellation takes effect at the end of your billing period.' },
	];
</script>

<section id="faq" class="py-20 md:py-28 px-4">
	<div class="max-w-2xl mx-auto">
		<div class="scroll-reveal text-center mb-14">
			<h2 class="text-2xl md:text-4xl font-bold mb-3">Questions</h2>
		</div>

		<div class="space-y-2">
			{#each faqs as faq, i}
				<div class="scroll-reveal scroll-reveal-delay-{Math.min(i + 1, 4)}">
					<button
						onclick={() => openIndex = openIndex === i ? -1 : i}
						class="w-full text-left bg-white/[0.03] border border-white/5 rounded-xl px-6 py-4 hover:bg-white/[0.05] transition-all duration-200 {openIndex === i ? 'border-white/10' : ''}"
					>
						<div class="flex justify-between items-center">
							<span class="font-semibold text-sm text-white/80">{faq.q}</span>
							<span class="text-white/30 text-xl transition-transform duration-300 {openIndex === i ? 'rotate-45' : ''}">+</span>
						</div>
						{#if openIndex === i}
							<p class="mt-3 text-sm text-white/40 leading-relaxed animate-fade-up">{faq.a}</p>
						{/if}
					</button>
				</div>
			{/each}
		</div>
	</div>
</section>
